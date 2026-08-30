//! Windows BMP/DIB layout used by retail `CDib`.
//!
//! The executable has two observable read paths. `CFile::Read` uses the packed
//! 14-byte `BITMAPFILEHEADER`'s `bfOffBits` as the pixel-stream split. The
//! mapped-file path passes the bytes after that header to `AttachMemory`, which
//! derives a contiguous 40-byte DIB header, palette, and pixel image and ignores
//! `bfOffBits`. The header's `biSize` field is exposed but neither path uses it
//! for layout. This module preserves both modes while bounds-checking all
//! borrowed slices and arithmetic.

use core::fmt;

pub const BITMAP_FILE_HEADER_SIZE: usize = 14;
pub const BITMAP_INFO_HEADER_SIZE: usize = 40;
pub const RGB_QUAD_SIZE: usize = 4;

const BITMAP_SIGNATURE: u16 = 0x4d42;
const DWORD_BITS: u32 = 32;
const DWORD_BYTES: u32 = 4;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BmpError {
    Truncated { at: usize, need: usize, have: usize },
    InvalidSignature { found: u16 },
    InvalidDimensions { width: i32, height: i32 },
    PixelOffsetBeforePalette { offset: usize, minimum: usize },
    SizeOverflow,
    WrongPaletteSize { need: usize, have: usize },
    WrongPixelSize { need: usize, have: usize },
    OutputTooSmall { need: usize, have: usize },
}

impl fmt::Display for BmpError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            BmpError::Truncated { at, need, have } => {
                write!(f, "bitmap has {have} byte(s) at offset {at}; need {need}")
            }
            BmpError::InvalidSignature { found } => {
                write!(f, "bitmap signature is 0x{found:04x}, not BM")
            }
            BmpError::InvalidDimensions { width, height } => {
                write!(f, "bitmap dimensions {width}x{height} are not positive")
            }
            BmpError::PixelOffsetBeforePalette { offset, minimum } => {
                write!(f, "pixel offset {offset} precedes palette end {minimum}")
            }
            BmpError::SizeOverflow => write!(f, "bitmap layout exceeds addressable size"),
            BmpError::WrongPaletteSize { need, have } => {
                write!(f, "palette is {have} bytes; retail layout needs {need}")
            }
            BmpError::WrongPixelSize { need, have } => {
                write!(f, "pixel image is {have} bytes; retail layout needs {need}")
            }
            BmpError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
        }
    }
}

impl core::error::Error for BmpError {}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BitmapFileHeader {
    pub file_size: u32,
    pub reserved_1: u16,
    pub reserved_2: u16,
    pub pixel_offset: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BitmapInfoHeader {
    pub header_size: u32,
    pub width: i32,
    pub height: i32,
    pub planes: u16,
    pub bit_count: u16,
    pub compression: u32,
    pub image_size: u32,
    pub x_pixels_per_meter: i32,
    pub y_pixels_per_meter: i32,
    pub colors_used: u32,
    pub colors_important: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DibMetrics {
    pub color_table_entries: u32,
    pub row_bytes: u32,
    pub image_bytes: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Dib<'a> {
    pub info: BitmapInfoHeader,
    pub metrics: DibMetrics,
    pub info_bytes: &'a [u8],
    pub color_table: &'a [u8],
    pub pixels: &'a [u8],
    pub trailing: &'a [u8],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Bmp<'a> {
    pub file: BitmapFileHeader,
    pub dib: Dib<'a>,
    pub pre_pixel_gap: &'a [u8],
}

fn bytes(src: &[u8], at: usize, len: usize) -> Result<&[u8], BmpError> {
    src.get(at..at.saturating_add(len))
        .ok_or(BmpError::Truncated {
            at,
            need: len,
            have: src.len().saturating_sub(at),
        })
}

fn read_u16(src: &[u8], at: usize) -> Result<u16, BmpError> {
    let value = bytes(src, at, 2)?;
    Ok(u16::from_le_bytes([value[0], value[1]]))
}

fn read_u32(src: &[u8], at: usize) -> Result<u32, BmpError> {
    let value = bytes(src, at, 4)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_i32(src: &[u8], at: usize) -> Result<i32, BmpError> {
    Ok(read_u32(src, at)? as i32)
}

pub fn parse_file_header(src: &[u8]) -> Result<BitmapFileHeader, BmpError> {
    let signature = read_u16(src, 0)?;
    if signature != BITMAP_SIGNATURE {
        return Err(BmpError::InvalidSignature { found: signature });
    }
    Ok(BitmapFileHeader {
        file_size: read_u32(src, 2)?,
        reserved_1: read_u16(src, 6)?,
        reserved_2: read_u16(src, 8)?,
        pixel_offset: read_u32(src, 10)?,
    })
}

pub fn parse_info_header(src: &[u8]) -> Result<BitmapInfoHeader, BmpError> {
    bytes(src, 0, BITMAP_INFO_HEADER_SIZE)?;
    Ok(BitmapInfoHeader {
        header_size: read_u32(src, 0)?,
        width: read_i32(src, 4)?,
        height: read_i32(src, 8)?,
        planes: read_u16(src, 12)?,
        bit_count: read_u16(src, 14)?,
        compression: read_u32(src, 16)?,
        image_size: read_u32(src, 20)?,
        x_pixels_per_meter: read_i32(src, 24)?,
        y_pixels_per_meter: read_i32(src, 28)?,
        colors_used: read_u32(src, 32)?,
        colors_important: read_u32(src, 36)?,
    })
}

/// Reproduce `CDib::ComputePaletteSize` for a valid bitmap bit depth.
pub const fn color_table_entries(bit_count: u16, colors_used: u32) -> u32 {
    if colors_used != 0 {
        colors_used
    } else {
        match bit_count {
            1 => 2,
            4 => 16,
            8 => 256,
            16 | 24 | 32 => 0,
            _ => 0,
        }
    }
}

/// Reproduce `CDib::ComputeMetrics`, rejecting only unsafe dimensions and
/// arithmetic overflow that retail would otherwise carry into a pointer.
pub fn compute_metrics(info: &BitmapInfoHeader) -> Result<DibMetrics, BmpError> {
    if info.width <= 0 || info.height <= 0 {
        return Err(BmpError::InvalidDimensions {
            width: info.width,
            height: info.height,
        });
    }
    let width = u32::try_from(info.width).map_err(|_| BmpError::SizeOverflow)?;
    let height = u32::try_from(info.height).map_err(|_| BmpError::SizeOverflow)?;
    let row_bits = width
        .checked_mul(u32::from(info.bit_count))
        .ok_or(BmpError::SizeOverflow)?;
    let row_dwords = row_bits
        .checked_div(DWORD_BITS)
        .and_then(|whole| whole.checked_add(u32::from(row_bits % DWORD_BITS != 0)))
        .ok_or(BmpError::SizeOverflow)?;
    let row_bytes = row_dwords
        .checked_mul(DWORD_BYTES)
        .ok_or(BmpError::SizeOverflow)?;
    let computed_image_bytes = row_bytes
        .checked_mul(height)
        .ok_or(BmpError::SizeOverflow)?;
    Ok(DibMetrics {
        color_table_entries: color_table_entries(info.bit_count, info.colors_used),
        row_bytes,
        image_bytes: if info.image_size != 0 {
            info.image_size
        } else {
            computed_image_bytes
        },
    })
}

/// Parse a headerless contiguous DIB payload as retail `CDib::AttachMemory`
/// does: fixed 40-byte header, derived palette, then the pixel image.
pub fn parse_dib(src: &[u8]) -> Result<Dib<'_>, BmpError> {
    let info = parse_info_header(src)?;
    let metrics = compute_metrics(&info)?;
    let palette_bytes = usize::try_from(metrics.color_table_entries)
        .map_err(|_| BmpError::SizeOverflow)?
        .checked_mul(RGB_QUAD_SIZE)
        .ok_or(BmpError::SizeOverflow)?;
    let pixel_at = BITMAP_INFO_HEADER_SIZE
        .checked_add(palette_bytes)
        .ok_or(BmpError::SizeOverflow)?;
    let image_bytes = usize::try_from(metrics.image_bytes).map_err(|_| BmpError::SizeOverflow)?;
    let end = pixel_at
        .checked_add(image_bytes)
        .ok_or(BmpError::SizeOverflow)?;
    bytes(src, 0, end)?;
    Ok(Dib {
        info,
        metrics,
        info_bytes: &src[..BITMAP_INFO_HEADER_SIZE],
        color_table: &src[BITMAP_INFO_HEADER_SIZE..pixel_at],
        pixels: &src[pixel_at..end],
        trailing: &src[end..],
    })
}

/// Parse the `CFile::Read` form, using `bfOffBits` as the pixel-stream split.
pub fn parse_bmp(src: &[u8]) -> Result<Bmp<'_>, BmpError> {
    let file = parse_file_header(src)?;
    let info_at = BITMAP_FILE_HEADER_SIZE;
    let info_bytes = bytes(src, info_at, BITMAP_INFO_HEADER_SIZE)?;
    let info = parse_info_header(info_bytes)?;
    let metrics = compute_metrics(&info)?;
    let palette_bytes = usize::try_from(metrics.color_table_entries)
        .map_err(|_| BmpError::SizeOverflow)?
        .checked_mul(RGB_QUAD_SIZE)
        .ok_or(BmpError::SizeOverflow)?;
    let palette_at = info_at + BITMAP_INFO_HEADER_SIZE;
    let palette_end = palette_at
        .checked_add(palette_bytes)
        .ok_or(BmpError::SizeOverflow)?;
    let pixel_at = usize::try_from(file.pixel_offset).map_err(|_| BmpError::SizeOverflow)?;
    if pixel_at < palette_end {
        return Err(BmpError::PixelOffsetBeforePalette {
            offset: pixel_at,
            minimum: palette_end,
        });
    }
    let image_bytes = usize::try_from(metrics.image_bytes).map_err(|_| BmpError::SizeOverflow)?;
    let end = pixel_at
        .checked_add(image_bytes)
        .ok_or(BmpError::SizeOverflow)?;
    bytes(src, 0, end)?;
    Ok(Bmp {
        file,
        dib: Dib {
            info,
            metrics,
            info_bytes,
            color_table: &src[palette_at..palette_end],
            pixels: &src[pixel_at..end],
            trailing: &src[end..],
        },
        pre_pixel_gap: &src[palette_end..pixel_at],
    })
}

/// Parse the mapped `AttachMemory` form: bytes after the file header are a
/// contiguous DIB and the recorded `bfOffBits` does not move the pixel slice.
pub fn parse_bmp_contiguous(src: &[u8]) -> Result<Bmp<'_>, BmpError> {
    let file = parse_file_header(src)?;
    let dib = parse_dib(bytes(
        src,
        BITMAP_FILE_HEADER_SIZE,
        src.len().saturating_sub(BITMAP_FILE_HEADER_SIZE),
    )?)?;
    Ok(Bmp {
        file,
        dib,
        pre_pixel_gap: &[],
    })
}

/// Write retail's packed BMP wrapper around exact DIB-header, palette, and
/// pixel bytes. The supplied slices must agree with the header-derived layout.
pub fn write_bmp(
    info_bytes: &[u8],
    color_table: &[u8],
    pixels: &[u8],
    output: &mut [u8],
) -> Result<usize, BmpError> {
    let info = parse_info_header(info_bytes)?;
    let metrics = compute_metrics(&info)?;
    let palette_need = usize::try_from(metrics.color_table_entries)
        .map_err(|_| BmpError::SizeOverflow)?
        .checked_mul(RGB_QUAD_SIZE)
        .ok_or(BmpError::SizeOverflow)?;
    if color_table.len() != palette_need {
        return Err(BmpError::WrongPaletteSize {
            need: palette_need,
            have: color_table.len(),
        });
    }
    let pixel_need = usize::try_from(metrics.image_bytes).map_err(|_| BmpError::SizeOverflow)?;
    if pixels.len() != pixel_need {
        return Err(BmpError::WrongPixelSize {
            need: pixel_need,
            have: pixels.len(),
        });
    }
    let pixel_at = BITMAP_FILE_HEADER_SIZE
        .checked_add(BITMAP_INFO_HEADER_SIZE)
        .and_then(|size| size.checked_add(palette_need))
        .ok_or(BmpError::SizeOverflow)?;
    let total = pixel_at
        .checked_add(pixel_need)
        .ok_or(BmpError::SizeOverflow)?;
    if output.len() < total {
        return Err(BmpError::OutputTooSmall {
            need: total,
            have: output.len(),
        });
    }
    let total_u32 = u32::try_from(total).map_err(|_| BmpError::SizeOverflow)?;
    let pixel_at_u32 = u32::try_from(pixel_at).map_err(|_| BmpError::SizeOverflow)?;
    output[..2].copy_from_slice(&BITMAP_SIGNATURE.to_le_bytes());
    output[2..6].copy_from_slice(&total_u32.to_le_bytes());
    output[6..10].fill(0);
    output[10..14].copy_from_slice(&pixel_at_u32.to_le_bytes());
    output[14..54].copy_from_slice(&info_bytes[..BITMAP_INFO_HEADER_SIZE]);
    output[54..pixel_at].copy_from_slice(color_table);
    output[pixel_at..total].copy_from_slice(pixels);
    Ok(total)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    fn info(width: i32, height: i32, bit_count: u16, image_size: u32, colors: u32) -> [u8; 40] {
        let mut out = [0u8; 40];
        out[0..4].copy_from_slice(&40u32.to_le_bytes());
        out[4..8].copy_from_slice(&width.to_le_bytes());
        out[8..12].copy_from_slice(&height.to_le_bytes());
        out[12..14].copy_from_slice(&1u16.to_le_bytes());
        out[14..16].copy_from_slice(&bit_count.to_le_bytes());
        out[20..24].copy_from_slice(&image_size.to_le_bytes());
        out[32..36].copy_from_slice(&colors.to_le_bytes());
        out
    }

    #[test]
    fn palette_rules_match_the_retail_switch() {
        assert_eq!(color_table_entries(1, 0), 2);
        assert_eq!(color_table_entries(4, 0), 16);
        assert_eq!(color_table_entries(8, 0), 256);
        assert_eq!(color_table_entries(16, 0), 0);
        assert_eq!(color_table_entries(24, 0), 0);
        assert_eq!(color_table_entries(32, 0), 0);
        assert_eq!(color_table_entries(24, 7), 7);
    }

    #[test]
    fn scanlines_are_dword_aligned() {
        let one = parse_info_header(&info(1, 1, 1, 0, 0)).unwrap();
        assert_eq!(compute_metrics(&one).unwrap().row_bytes, 4);
        assert_eq!(compute_metrics(&one).unwrap().image_bytes, 4);

        let odd = parse_info_header(&info(17, 2, 4, 0, 0)).unwrap();
        assert_eq!(compute_metrics(&odd).unwrap().row_bytes, 12);
        assert_eq!(compute_metrics(&odd).unwrap().image_bytes, 24);

        let rgb = parse_info_header(&info(3, 2, 24, 0, 0)).unwrap();
        assert_eq!(compute_metrics(&rgb).unwrap().row_bytes, 12);
        assert_eq!(compute_metrics(&rgb).unwrap().image_bytes, 24);
    }

    #[test]
    fn nonzero_image_size_is_authoritative() {
        let header = parse_info_header(&info(3, 2, 24, 99, 0)).unwrap();
        assert_eq!(compute_metrics(&header).unwrap().image_bytes, 99);
    }

    #[test]
    fn bmp_round_trip_preserves_exact_dib_bytes() {
        let header = info(3, 2, 24, 0, 0);
        let pixels = [0x5au8; 24];
        let mut encoded = [0u8; 78];
        assert_eq!(write_bmp(&header, &[], &pixels, &mut encoded).unwrap(), 78);
        let parsed = parse_bmp(&encoded).unwrap();
        assert_eq!(parsed.file.file_size, 78);
        assert_eq!(parsed.file.pixel_offset, 54);
        assert_eq!(parsed.dib.info_bytes, &header);
        assert_eq!(parsed.dib.pixels, &pixels);
        assert!(parsed.dib.trailing.is_empty());
        assert!(parsed.pre_pixel_gap.is_empty());
    }

    #[test]
    fn mapped_parser_uses_contiguous_offset_not_bf_off_bits() {
        let header = info(1, 1, 1, 0, 0);
        let palette = [0x11u8; 8];
        let pixels = [0x22u8; 4];
        let mut encoded = [0u8; 66];
        write_bmp(&header, &palette, &pixels, &mut encoded).unwrap();
        encoded[10..14].copy_from_slice(&0x1234_5678u32.to_le_bytes());
        let parsed = parse_bmp_contiguous(&encoded).unwrap();
        assert_eq!(parsed.file.pixel_offset, 0x1234_5678);
        assert_eq!(parsed.dib.color_table, &palette);
        assert_eq!(parsed.dib.pixels, &pixels);
    }

    #[test]
    fn cfile_parser_honors_bf_off_bits_and_exposes_the_gap() {
        let header = info(1, 1, 24, 0, 0);
        let pixels = [0x33u8; 4];
        let mut encoded = [0u8; 62];
        encoded[0..2].copy_from_slice(b"BM");
        encoded[2..6].copy_from_slice(&62u32.to_le_bytes());
        encoded[10..14].copy_from_slice(&58u32.to_le_bytes());
        encoded[14..54].copy_from_slice(&header);
        encoded[54..58].copy_from_slice(&[1, 2, 3, 4]);
        encoded[58..62].copy_from_slice(&pixels);
        let parsed = parse_bmp(&encoded).unwrap();
        assert_eq!(parsed.pre_pixel_gap, &[1, 2, 3, 4]);
        assert_eq!(parsed.dib.pixels, &pixels);
    }

    #[test]
    fn malformed_inputs_fail_without_partial_views() {
        assert!(matches!(
            parse_bmp(b"ZZ"),
            Err(BmpError::InvalidSignature { .. })
        ));
        let header = info(1, 1, 8, 0, 0);
        let mut short = vec![0u8; 14 + 40];
        short[0..2].copy_from_slice(b"BM");
        short[10..14].copy_from_slice(&1078u32.to_le_bytes());
        short[14..].copy_from_slice(&header);
        assert!(matches!(parse_bmp(&short), Err(BmpError::Truncated { .. })));
        assert!(matches!(
            compute_metrics(&parse_info_header(&info(-1, 2, 24, 0, 0)).unwrap()),
            Err(BmpError::InvalidDimensions { .. })
        ));
    }
}
