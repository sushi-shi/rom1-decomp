//! MFC ANSI-string and recovered TableLine archive layouts.
//!
//! Retail uses the VC5 SP2 `CArchive` CString grammar:
//!
//! ```text
//! len < 0xff:   u8 len
//! len < 0xfffe: u8 0xff, u16 len
//! otherwise:    u8 0xff, u16 0xffff, u32 len
//! u8 bytes[len]
//! ```
//!
//! Embedded CObject fields dispatch another serializer and therefore have no
//! intrinsic extent here. The compositional APIs accept those already-encoded
//! bytes, or an exact nested extent while parsing, instead of inventing a
//! boundary that retail does not store.

use core::fmt;

const BYTE_EXTENDED: u8 = 0xff;
const WORD_EXTENDED: u16 = 0xffff;
const UNICODE_MARKER: u16 = 0xfffe;
pub const WORD_BLOCK_BYTES: usize = 10;
pub const RAW_BLOCK_BYTES: usize = 0x48;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TableLineError {
    Truncated { at: usize, need: usize, have: usize },
    SizeOverflow,
    OutputTooSmall { need: usize, have: usize },
    UnicodeStringUnsupported,
}

impl fmt::Display for TableLineError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            TableLineError::Truncated { at, need, have } => {
                write!(f, "archive has {have} byte(s) at offset {at}; need {need}")
            }
            TableLineError::SizeOverflow => write!(f, "TableLine archive size overflows"),
            TableLineError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
            TableLineError::UnicodeStringUnsupported => {
                write!(
                    f,
                    "VC5 Unicode CString conversion requires a Windows code page"
                )
            }
        }
    }
}

impl core::error::Error for TableLineError {}

fn take(src: &[u8], at: usize, need: usize) -> Result<&[u8], TableLineError> {
    let end = at.checked_add(need).ok_or(TableLineError::SizeOverflow)?;
    src.get(at..end).ok_or(TableLineError::Truncated {
        at,
        need,
        have: src.len().saturating_sub(at),
    })
}

fn checked_add(left: usize, right: usize) -> Result<usize, TableLineError> {
    left.checked_add(right).ok_or(TableLineError::SizeOverflow)
}

fn ensure_output(dst: &[u8], need: usize) -> Result<(), TableLineError> {
    if dst.len() < need {
        Err(TableLineError::OutputTooSmall {
            need,
            have: dst.len(),
        })
    } else {
        Ok(())
    }
}

fn copy_at(dst: &mut [u8], at: &mut usize, bytes: &[u8]) {
    let end = *at + bytes.len();
    dst[*at..end].copy_from_slice(bytes);
    *at = end;
}

pub fn ansi_string_encoded_len(length: usize) -> Result<usize, TableLineError> {
    let prefix = if length < usize::from(BYTE_EXTENDED) {
        1
    } else if length < usize::from(UNICODE_MARKER) {
        3
    } else {
        u32::try_from(length).map_err(|_| TableLineError::SizeOverflow)?;
        7
    };
    checked_add(prefix, length)
}

fn encode_ansi_string_at(
    bytes: &[u8],
    dst: &mut [u8],
    at: &mut usize,
) -> Result<(), TableLineError> {
    if bytes.len() < usize::from(BYTE_EXTENDED) {
        dst[*at] = bytes.len() as u8;
        *at += 1;
    } else if bytes.len() < usize::from(UNICODE_MARKER) {
        dst[*at] = BYTE_EXTENDED;
        *at += 1;
        copy_at(dst, at, &(bytes.len() as u16).to_le_bytes());
    } else {
        let length = u32::try_from(bytes.len()).map_err(|_| TableLineError::SizeOverflow)?;
        dst[*at] = BYTE_EXTENDED;
        *at += 1;
        copy_at(dst, at, &WORD_EXTENDED.to_le_bytes());
        copy_at(dst, at, &length.to_le_bytes());
    }
    copy_at(dst, at, bytes);
    Ok(())
}

pub fn encode_ansi_string_into(bytes: &[u8], dst: &mut [u8]) -> Result<usize, TableLineError> {
    let need = ansi_string_encoded_len(bytes.len())?;
    ensure_output(dst, need)?;
    let mut at = 0;
    encode_ansi_string_at(bytes, dst, &mut at)?;
    Ok(at)
}

fn parse_ansi_string_at<'a>(src: &'a [u8], at: usize) -> Result<(&'a [u8], usize), TableLineError> {
    let first = take(src, at, 1)?[0];
    let (length, bytes_at) = if first != BYTE_EXTENDED {
        (usize::from(first), checked_add(at, 1)?)
    } else {
        let word_at = checked_add(at, 1)?;
        let word = take(src, word_at, 2)?;
        let length16 = u16::from_le_bytes([word[0], word[1]]);
        if length16 == UNICODE_MARKER {
            return Err(TableLineError::UnicodeStringUnsupported);
        }
        if length16 != WORD_EXTENDED {
            (usize::from(length16), checked_add(word_at, 2)?)
        } else {
            let dword_at = checked_add(word_at, 2)?;
            let dword = take(src, dword_at, 4)?;
            (
                u32::from_le_bytes([dword[0], dword[1], dword[2], dword[3]]) as usize,
                checked_add(dword_at, 4)?,
            )
        }
    };
    let bytes = take(src, bytes_at, length)?;
    Ok((bytes, checked_add(bytes_at, length)?))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AnsiString<'a> {
    pub bytes: &'a [u8],
    pub trailing: &'a [u8],
}

pub fn parse_ansi_string(src: &[u8]) -> Result<AnsiString<'_>, TableLineError> {
    let (bytes, end) = parse_ansi_string_at(src, 0)?;
    Ok(AnsiString {
        bytes,
        trailing: &src[end..],
    })
}

fn base_len(name: &[u8], nested: &[u8]) -> Result<usize, TableLineError> {
    checked_add(ansi_string_encoded_len(name.len())?, nested.len())
}

fn encode_base_at(
    name: &[u8],
    nested: &[u8],
    dst: &mut [u8],
    at: &mut usize,
) -> Result<(), TableLineError> {
    encode_ansi_string_at(name, dst, at)?;
    copy_at(dst, at, nested);
    Ok(())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TableLine<'a> {
    pub name: &'a [u8],
    pub nested: &'a [u8],
    pub trailing: &'a [u8],
}

pub fn encode_table_line_into(
    name: &[u8],
    nested: &[u8],
    dst: &mut [u8],
) -> Result<usize, TableLineError> {
    let need = base_len(name, nested)?;
    ensure_output(dst, need)?;
    let mut at = 0;
    encode_base_at(name, nested, dst, &mut at)?;
    Ok(at)
}

pub fn parse_table_line(src: &[u8], nested_len: usize) -> Result<TableLine<'_>, TableLineError> {
    let (name, at) = parse_ansi_string_at(src, 0)?;
    let nested = take(src, at, nested_len)?;
    let end = checked_add(at, nested_len)?;
    Ok(TableLine {
        name,
        nested,
        trailing: &src[end..],
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct WordBlock<'a> {
    pub name: &'a [u8],
    pub base_nested: &'a [u8],
    pub words: &'a [u8],
    pub strings_nested: &'a [u8],
    pub trailing: &'a [u8],
}

pub fn encode_word_block_into(
    name: &[u8],
    base_nested: &[u8],
    words: &[u8; WORD_BLOCK_BYTES],
    strings_nested: &[u8],
    dst: &mut [u8],
) -> Result<usize, TableLineError> {
    let need = checked_add(
        checked_add(base_len(name, base_nested)?, words.len())?,
        strings_nested.len(),
    )?;
    ensure_output(dst, need)?;
    let mut at = 0;
    encode_base_at(name, base_nested, dst, &mut at)?;
    copy_at(dst, &mut at, words);
    copy_at(dst, &mut at, strings_nested);
    Ok(at)
}

pub fn parse_word_block(
    src: &[u8],
    base_nested_len: usize,
    strings_nested_len: usize,
) -> Result<WordBlock<'_>, TableLineError> {
    let (name, mut at) = parse_ansi_string_at(src, 0)?;
    let base_nested = take(src, at, base_nested_len)?;
    at = checked_add(at, base_nested_len)?;
    let words = take(src, at, WORD_BLOCK_BYTES)?;
    at = checked_add(at, WORD_BLOCK_BYTES)?;
    let strings_nested = take(src, at, strings_nested_len)?;
    at = checked_add(at, strings_nested_len)?;
    Ok(WordBlock {
        name,
        base_nested,
        words,
        strings_nested,
        trailing: &src[at..],
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RawBlock<'a> {
    pub name: &'a [u8],
    pub bytes: &'a [u8],
    pub trailing: &'a [u8],
}

pub fn encode_raw_block_into(
    name: &[u8],
    bytes: &[u8; RAW_BLOCK_BYTES],
    dst: &mut [u8],
) -> Result<usize, TableLineError> {
    let need = checked_add(ansi_string_encoded_len(name.len())?, bytes.len())?;
    ensure_output(dst, need)?;
    let mut at = 0;
    encode_ansi_string_at(name, dst, &mut at)?;
    copy_at(dst, &mut at, bytes);
    Ok(at)
}

pub fn parse_raw_block(src: &[u8]) -> Result<RawBlock<'_>, TableLineError> {
    let (name, at) = parse_ansi_string_at(src, 0)?;
    let bytes = take(src, at, RAW_BLOCK_BYTES)?;
    let end = checked_add(at, RAW_BLOCK_BYTES)?;
    Ok(RawBlock {
        name,
        bytes,
        trailing: &src[end..],
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct WordBlockLabel<'a> {
    pub name: &'a [u8],
    pub base_nested: &'a [u8],
    pub first_word_byte: u8,
    pub label: &'a [u8],
    pub trailing: &'a [u8],
}

pub fn encode_word_block_label_into(
    name: &[u8],
    base_nested: &[u8],
    first_word_byte: u8,
    label: &[u8],
    dst: &mut [u8],
) -> Result<usize, TableLineError> {
    let need = checked_add(
        checked_add(base_len(name, base_nested)?, 1)?,
        ansi_string_encoded_len(label.len())?,
    )?;
    ensure_output(dst, need)?;
    let mut at = 0;
    encode_base_at(name, base_nested, dst, &mut at)?;
    dst[at] = first_word_byte;
    at += 1;
    encode_ansi_string_at(label, dst, &mut at)?;
    Ok(at)
}

pub fn parse_word_block_label(
    src: &[u8],
    base_nested_len: usize,
) -> Result<WordBlockLabel<'_>, TableLineError> {
    let (name, mut at) = parse_ansi_string_at(src, 0)?;
    let base_nested = take(src, at, base_nested_len)?;
    at = checked_add(at, base_nested_len)?;
    let first_word_byte = take(src, at, 1)?[0];
    at = checked_add(at, 1)?;
    let (label, end) = parse_ansi_string_at(src, at)?;
    Ok(WordBlockLabel {
        name,
        base_nested,
        first_word_byte,
        label,
        trailing: &src[end..],
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Label<'a> {
    pub name: &'a [u8],
    pub base_nested: &'a [u8],
    pub label: &'a [u8],
    pub trailing: &'a [u8],
}

pub fn encode_label_into(
    name: &[u8],
    base_nested: &[u8],
    label: &[u8],
    dst: &mut [u8],
) -> Result<usize, TableLineError> {
    let need = checked_add(
        base_len(name, base_nested)?,
        ansi_string_encoded_len(label.len())?,
    )?;
    ensure_output(dst, need)?;
    let mut at = 0;
    encode_base_at(name, base_nested, dst, &mut at)?;
    encode_ansi_string_at(label, dst, &mut at)?;
    Ok(at)
}

pub fn parse_label(src: &[u8], base_nested_len: usize) -> Result<Label<'_>, TableLineError> {
    let (name, mut at) = parse_ansi_string_at(src, 0)?;
    let base_nested = take(src, at, base_nested_len)?;
    at = checked_add(at, base_nested_len)?;
    let (label, end) = parse_ansi_string_at(src, at)?;
    Ok(Label {
        name,
        base_nested,
        label,
        trailing: &src[end..],
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StringGroup<'a> {
    pub name: &'a [u8],
    pub base_nested: &'a [u8],
    encoded_strings: &'a [u8],
    pub trailing: &'a [u8],
    count: usize,
}

impl<'a> StringGroup<'a> {
    pub const fn len(self) -> usize {
        self.count
    }

    pub const fn is_empty(self) -> bool {
        self.count == 0
    }

    pub const fn strings(self) -> StringGroupIter<'a> {
        StringGroupIter {
            encoded: self.encoded_strings,
            at: 0,
            remaining: self.count,
        }
    }
}

pub struct StringGroupIter<'a> {
    encoded: &'a [u8],
    at: usize,
    remaining: usize,
}

impl<'a> Iterator for StringGroupIter<'a> {
    type Item = &'a [u8];

    fn next(&mut self) -> Option<Self::Item> {
        if self.remaining == 0 {
            return None;
        }
        let (bytes, end) = parse_ansi_string_at(self.encoded, self.at).ok()?;
        self.at = end;
        self.remaining -= 1;
        Some(bytes)
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.remaining, Some(self.remaining))
    }
}

impl ExactSizeIterator for StringGroupIter<'_> {}

pub fn encode_string_group_into(
    name: &[u8],
    base_nested: &[u8],
    strings: &[&[u8]],
    dst: &mut [u8],
) -> Result<usize, TableLineError> {
    let mut need = base_len(name, base_nested)?;
    for string in strings {
        need = checked_add(need, ansi_string_encoded_len(string.len())?)?;
    }
    ensure_output(dst, need)?;
    let mut at = 0;
    encode_base_at(name, base_nested, dst, &mut at)?;
    for string in strings {
        encode_ansi_string_at(string, dst, &mut at)?;
    }
    Ok(at)
}

pub fn parse_string_group(
    src: &[u8],
    base_nested_len: usize,
    count: usize,
) -> Result<StringGroup<'_>, TableLineError> {
    let (name, mut at) = parse_ansi_string_at(src, 0)?;
    let base_nested = take(src, at, base_nested_len)?;
    at = checked_add(at, base_nested_len)?;
    let strings_at = at;
    for _ in 0..count {
        let (_, end) = parse_ansi_string_at(src, at)?;
        at = end;
    }
    Ok(StringGroup {
        name,
        base_nested,
        encoded_strings: &src[strings_at..at],
        trailing: &src[at..],
        count,
    })
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    #[test]
    fn ansi_string_prefix_boundaries_match_vc5_sp2_retail() {
        let lengths = [0, 1, 254, 255, 256, 65533, 65534];
        for length in lengths {
            let input = vec![0x5a; length];
            let mut encoded = vec![0; ansi_string_encoded_len(length).unwrap()];
            let size = encode_ansi_string_into(&input, &mut encoded).unwrap();
            assert_eq!(size, encoded.len());
            match length {
                0 => assert_eq!(&encoded[..1], &[0]),
                1 => assert_eq!(&encoded[..1], &[1]),
                254 => assert_eq!(&encoded[..1], &[0xfe]),
                255 => assert_eq!(&encoded[..3], &[0xff, 0xff, 0x00]),
                256 => assert_eq!(&encoded[..3], &[0xff, 0x00, 0x01]),
                65533 => assert_eq!(&encoded[..3], &[0xff, 0xfd, 0xff]),
                65534 => {
                    assert_eq!(&encoded[..7], &[0xff, 0xff, 0xff, 0xfe, 0xff, 0x00, 0x00])
                }
                _ => unreachable!(),
            }
            let parsed = parse_ansi_string(&encoded).unwrap();
            assert_eq!(parsed.bytes, input);
            assert!(parsed.trailing.is_empty());
        }
    }

    #[test]
    fn ansi_parser_rejects_truncation_and_unicode_conversion() {
        assert_eq!(
            parse_ansi_string(&[0xff, 0xfe, 0xff]),
            Err(TableLineError::UnicodeStringUnsupported)
        );
        assert!(matches!(
            parse_ansi_string(&[0xff, 0xff, 0xff, 4, 0]),
            Err(TableLineError::Truncated { .. })
        ));
        assert!(matches!(
            parse_ansi_string(&[3, b'a']),
            Err(TableLineError::Truncated { .. })
        ));
    }

    #[test]
    fn base_and_label_layouts_round_trip_compositionally() {
        let mut bytes = [0; 64];
        let size = encode_table_line_into(b"base", &[1, 2, 3, 4], &mut bytes).unwrap();
        let parsed = parse_table_line(&bytes[..size], 4).unwrap();
        assert_eq!(parsed.name, b"base");
        assert_eq!(parsed.nested, [1, 2, 3, 4]);

        let size = encode_label_into(b"base", &[1, 2, 3, 4], b"label", &mut bytes).unwrap();
        let parsed = parse_label(&bytes[..size], 4).unwrap();
        assert_eq!(parsed.name, b"base");
        assert_eq!(parsed.base_nested, [1, 2, 3, 4]);
        assert_eq!(parsed.label, b"label");
    }

    #[test]
    fn raw_and_word_block_layouts_preserve_exact_bytes() {
        let raw = [0x7c; RAW_BLOCK_BYTES];
        let words = [0x35; WORD_BLOCK_BYTES];
        let mut bytes = [0; 128];
        let size = encode_raw_block_into(b"raw", &raw, &mut bytes).unwrap();
        let parsed = parse_raw_block(&bytes[..size]).unwrap();
        assert_eq!(parsed.name, b"raw");
        assert_eq!(parsed.bytes, raw);

        let size =
            encode_word_block_into(b"words", &[1, 2, 3, 4], &words, &[5, 6, 7, 8], &mut bytes)
                .unwrap();
        let parsed = parse_word_block(&bytes[..size], 4, 4).unwrap();
        assert_eq!(parsed.words, words);
        assert_eq!(parsed.base_nested, [1, 2, 3, 4]);
        assert_eq!(parsed.strings_nested, [5, 6, 7, 8]);
    }

    #[test]
    fn first_word_byte_and_string_groups_match_retail_field_order() {
        let mut bytes = [0; 128];
        let size =
            encode_word_block_label_into(b"N", &[0x44, 0x33, 0x22, 0x11], 0xa5, b"L", &mut bytes)
                .unwrap();
        assert_eq!(
            &bytes[..size],
            &[1, b'N', 0x44, 0x33, 0x22, 0x11, 0xa5, 1, b'L']
        );
        let parsed = parse_word_block_label(&bytes[..size], 4).unwrap();
        assert_eq!(parsed.first_word_byte, 0xa5);
        assert_eq!(parsed.label, b"L");

        let strings: &[&[u8]] = &[b"A", b"BC"];
        let size =
            encode_string_group_into(b"N", &[0x44, 0x33, 0x22, 0x11], strings, &mut bytes).unwrap();
        assert_eq!(
            &bytes[..size],
            &[1, b'N', 0x44, 0x33, 0x22, 0x11, 1, b'A', 2, b'B', b'C']
        );
        let parsed = parse_string_group(&bytes[..size], 4, 2).unwrap();
        assert_eq!(parsed.strings().collect::<std::vec::Vec<_>>(), strings);
    }

    #[test]
    fn safe_writers_report_required_capacity_without_partial_claims() {
        let mut tiny = [0xcc; 2];
        assert_eq!(
            encode_label_into(b"name", &[1, 2, 3, 4], b"label", &mut tiny),
            Err(TableLineError::OutputTooSmall { need: 15, have: 2 })
        );
        assert_eq!(tiny, [0xcc; 2]);
    }
}
