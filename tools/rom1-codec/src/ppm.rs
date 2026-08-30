//! Netpbm P3/P6 parsing as implemented by retail `CPixMap::LoadPPM`.
//!
//! This is intentionally not a general Netpbm parser. Retail reads through a
//! 100-byte `fgets` buffer, recognizes only the first two magic bytes, skips
//! only full lines whose first byte is `#` between the magic and dimensions,
//! parses both dimensions from one line, and discards exactly one max-value
//! line without interpreting it. P3 components are decimal `int` values
//! truncated to `u8`; P6 components are copied verbatim.

use core::fmt;

const RETAIL_LINE_BUFFER: usize = 100;
const RETAIL_LINE_PAYLOAD: usize = RETAIL_LINE_BUFFER - 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PpmEncoding {
    AsciiP3,
    BinaryP6,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PpmInfo {
    /// `None` reproduces retail's successful no-op for an unknown magic.
    pub encoding: Option<PpmEncoding>,
    pub width: i32,
    pub height: i32,
    pub pixel_bytes: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PpmError {
    Truncated { at: usize, need: usize, have: usize },
    InvalidInteger { at: usize },
    InvalidDimensions { width: i32, height: i32 },
    SizeOverflow,
    OutputTooSmall { need: usize, have: usize },
}

impl fmt::Display for PpmError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            PpmError::Truncated { at, need, have } => {
                write!(f, "PPM has {have} byte(s) at offset {at}; need {need}")
            }
            PpmError::InvalidInteger { at } => {
                write!(f, "PPM has no valid decimal integer at offset {at}")
            }
            PpmError::InvalidDimensions { width, height } => {
                write!(f, "PPM dimensions {width}x{height} are not positive")
            }
            PpmError::SizeOverflow => write!(f, "PPM pixel count exceeds addressable size"),
            PpmError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
        }
    }
}

impl core::error::Error for PpmError {}

#[derive(Debug, Clone, Copy)]
struct Layout {
    info: PpmInfo,
    pixels_at: usize,
}

fn fgets_line(src: &[u8], at: usize) -> Result<(&[u8], usize), PpmError> {
    if at >= src.len() {
        return Err(PpmError::Truncated {
            at,
            need: 1,
            have: 0,
        });
    }
    let limit = src.len().min(at.saturating_add(RETAIL_LINE_PAYLOAD));
    let mut end = at;
    while end < limit {
        end += 1;
        if src[end - 1] == b'\n' {
            break;
        }
    }
    Ok((&src[at..end], end))
}

const fn is_c_space(byte: u8) -> bool {
    byte == b' ' || (byte >= b'\t' && byte <= b'\r')
}

fn scan_i32(src: &[u8], cursor: &mut usize) -> Result<i32, PpmError> {
    while *cursor < src.len() && is_c_space(src[*cursor]) {
        *cursor += 1;
    }
    let start = *cursor;
    let negative = match src.get(*cursor) {
        Some(b'-') => {
            *cursor += 1;
            true
        }
        Some(b'+') => {
            *cursor += 1;
            false
        }
        _ => false,
    };
    let digits_at = *cursor;
    let mut value = 0u64;
    let limit = if negative {
        2_147_483_648u64
    } else {
        2_147_483_647u64
    };
    while let Some(byte @ b'0'..=b'9') = src.get(*cursor).copied() {
        value = value
            .checked_mul(10)
            .and_then(|current| current.checked_add(u64::from(byte - b'0')))
            .ok_or(PpmError::InvalidInteger { at: start })?;
        if value > limit {
            return Err(PpmError::InvalidInteger { at: start });
        }
        *cursor += 1;
    }
    if *cursor == digits_at {
        return Err(PpmError::InvalidInteger { at: start });
    }
    let signed = if negative {
        -(value as i64)
    } else {
        value as i64
    };
    Ok(signed as i32)
}

fn parse_dimensions(line: &[u8], source_at: usize) -> Result<(i32, i32), PpmError> {
    let mut cursor = 0;
    let width = scan_i32(line, &mut cursor).map_err(|error| match error {
        PpmError::InvalidInteger { at } => PpmError::InvalidInteger { at: source_at + at },
        other => other,
    })?;
    let height = scan_i32(line, &mut cursor).map_err(|error| match error {
        PpmError::InvalidInteger { at } => PpmError::InvalidInteger { at: source_at + at },
        other => other,
    })?;
    if width <= 0 || height <= 0 {
        return Err(PpmError::InvalidDimensions { width, height });
    }
    Ok((width, height))
}

fn pixel_bytes(width: i32, height: i32) -> Result<usize, PpmError> {
    let bytes = width
        .checked_mul(height)
        .and_then(|pixels| pixels.checked_mul(3))
        .ok_or(PpmError::SizeOverflow)?;
    usize::try_from(bytes).map_err(|_| PpmError::SizeOverflow)
}

fn parse_layout(src: &[u8]) -> Result<Layout, PpmError> {
    let (magic, mut at) = fgets_line(src, 0)?;
    if magic.len() < 2 {
        return Err(PpmError::Truncated {
            at: 0,
            need: 2,
            have: magic.len(),
        });
    }
    let encoding = match &magic[..2] {
        b"P3" => PpmEncoding::AsciiP3,
        b"P6" => PpmEncoding::BinaryP6,
        _ => {
            return Ok(Layout {
                info: PpmInfo {
                    encoding: None,
                    width: 0,
                    height: 0,
                    pixel_bytes: 0,
                },
                pixels_at: at,
            });
        }
    };

    let (dimensions, dimensions_at) = loop {
        let line_at = at;
        let (line, next) = fgets_line(src, at)?;
        at = next;
        if line.first() != Some(&b'#') {
            break (line, line_at);
        }
    };
    let (width, height) = parse_dimensions(dimensions, dimensions_at)?;
    let (_, pixels_at) = fgets_line(src, at)?;
    let pixel_bytes = pixel_bytes(width, height)?;
    Ok(Layout {
        info: PpmInfo {
            encoding: Some(encoding),
            width,
            height,
            pixel_bytes,
        },
        pixels_at,
    })
}

/// Inspect the retail PPM header and report the caller-owned output size.
pub fn inspect_ppm(src: &[u8]) -> Result<PpmInfo, PpmError> {
    Ok(parse_layout(src)?.info)
}

/// Decode retail's P3/P6 subset into `output`.
///
/// Unknown magic reproduces retail's successful no-op and writes nothing.
/// Inputs that would make retail consume uninitialized memory, wrap signed
/// allocation arithmetic, or overrun its allocation are rejected.
pub fn decode_ppm(src: &[u8], output: &mut [u8]) -> Result<PpmInfo, PpmError> {
    let layout = parse_layout(src)?;
    if layout.info.encoding.is_none() {
        return Ok(layout.info);
    }
    if output.len() < layout.info.pixel_bytes {
        return Err(PpmError::OutputTooSmall {
            need: layout.info.pixel_bytes,
            have: output.len(),
        });
    }

    match layout.info.encoding {
        Some(PpmEncoding::BinaryP6) => {
            let have = src.len().saturating_sub(layout.pixels_at);
            let pixels = src
                .get(layout.pixels_at..layout.pixels_at + layout.info.pixel_bytes)
                .ok_or(PpmError::Truncated {
                    at: layout.pixels_at,
                    need: layout.info.pixel_bytes,
                    have,
                })?;
            output[..layout.info.pixel_bytes].copy_from_slice(pixels);
        }
        Some(PpmEncoding::AsciiP3) => {
            let mut cursor = layout.pixels_at;
            for slot in &mut output[..layout.info.pixel_bytes] {
                *slot = scan_i32(src, &mut cursor)? as u8;
            }
        }
        None => {}
    }
    Ok(layout.info)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    #[test]
    fn binary_p6_skips_header_comments_and_copies_bytes() {
        let src = b"P6\n# one\n# two\n2 1\n999\n\0\xff#\n\x80\x01trailing";
        let mut output = [0u8; 6];
        let info = decode_ppm(src, &mut output).unwrap();
        assert_eq!(
            info,
            PpmInfo {
                encoding: Some(PpmEncoding::BinaryP6),
                width: 2,
                height: 1,
                pixel_bytes: 6,
            }
        );
        assert_eq!(output, [0, 255, b'#', b'\n', 128, 1]);
    }

    #[test]
    fn ascii_p3_truncates_signed_int_components() {
        let src = b"P3\n1 2\n1\n-1 +256 511\n-258 1024 7 ignored";
        let mut output = [0u8; 6];
        decode_ppm(src, &mut output).unwrap();
        assert_eq!(output, [255, 0, 255, 254, 0, 7]);
    }

    #[test]
    fn max_value_line_is_discarded_without_parsing() {
        let src = b"P3\n1 1\nthis is not a number\n1 2 3";
        let mut output = [0u8; 3];
        decode_ppm(src, &mut output).unwrap();
        assert_eq!(output, [1, 2, 3]);
    }

    #[test]
    fn only_comments_at_column_zero_before_dimensions_are_skipped() {
        let src = b"P3\n # not a retail comment\n1 1\n255\n1 2 3";
        assert!(matches!(
            inspect_ppm(src),
            Err(PpmError::InvalidInteger { .. })
        ));
    }

    #[test]
    fn unknown_magic_is_a_successful_no_op() {
        let mut output = [0xa5u8; 4];
        assert_eq!(
            decode_ppm(b"P9\nanything", &mut output).unwrap(),
            PpmInfo {
                encoding: None,
                width: 0,
                height: 0,
                pixel_bytes: 0,
            }
        );
        assert_eq!(output, [0xa5; 4]);
    }

    #[test]
    fn fgets_limit_is_part_of_the_grammar() {
        let mut src = vec![b' '; 99];
        src[0] = b'P';
        src[1] = b'3';
        src.extend_from_slice(b"2 1\n255\n1 2 3 4 5 6");
        let mut output = [0u8; 6];
        decode_ppm(&src, &mut output).unwrap();
        assert_eq!(output, [1, 2, 3, 4, 5, 6]);
    }

    #[test]
    fn rejects_unsafe_retail_reads_and_allocations() {
        assert!(matches!(
            inspect_ppm(b"P6\n0 1\n255\n"),
            Err(PpmError::InvalidDimensions { .. })
        ));
        assert!(matches!(
            inspect_ppm(b"P6\n2147483647 2147483647\n255\n"),
            Err(PpmError::SizeOverflow)
        ));
        assert!(matches!(
            decode_ppm(b"P6\n1 1\n255\n\x01\x02", &mut [0u8; 3]),
            Err(PpmError::Truncated { .. })
        ));
        assert!(matches!(
            decode_ppm(b"P3\n1 1\n255\n1 2", &mut [0u8; 3]),
            Err(PpmError::InvalidInteger { .. })
        ));
        assert!(matches!(
            decode_ppm(b"P6\n1 1\n255\n\x01\x02\x03", &mut [0u8; 2]),
            Err(PpmError::OutputTooSmall { need: 3, have: 2 })
        ));
    }
}
