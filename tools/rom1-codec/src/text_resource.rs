//! Startup text resources loaded by `CTextBlock::Load` at `0x068660`.
//!
//! Retail reads the entire resource into one allocation. For each record it
//! scans for `CR`, replaces that byte with NUL, and advances by two bytes,
//! blindly consuming the byte after `CR`. Shipped resources use `CR LF`, but
//! the second separator byte is not tested by the executable. This parser
//! exposes it instead of silently normalizing the retail behavior.

use core::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TextResourceError {
    /// Retail's do-while loop would dereference a zero-byte allocation.
    Empty,
    UnterminatedLine {
        at: usize,
    },
    MissingSeparatorTail {
        at: usize,
    },
    CarriageReturnInLine {
        line: usize,
        at: usize,
    },
    SizeOverflow,
    OutputTooSmall {
        need: usize,
        have: usize,
    },
}

impl fmt::Display for TextResourceError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            TextResourceError::Empty => write!(f, "text resource is empty"),
            TextResourceError::UnterminatedLine { at } => {
                write!(f, "text record at offset {at} has no CR terminator")
            }
            TextResourceError::MissingSeparatorTail { at } => {
                write!(f, "CR at offset {at} has no following separator byte")
            }
            TextResourceError::CarriageReturnInLine { line, at } => {
                write!(f, "line {line} contains CR at byte {at}")
            }
            TextResourceError::SizeOverflow => write!(f, "encoded text size overflows usize"),
            TextResourceError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
        }
    }
}

impl core::error::Error for TextResourceError {}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TextRecord<'a> {
    bytes: &'a [u8],
    separator_tail: u8,
}

impl<'a> TextRecord<'a> {
    pub const fn bytes(self) -> &'a [u8] {
        self.bytes
    }

    /// The byte retail skips immediately after the terminating CR. Shipped
    /// data uses LF, though the loader itself does not check that value.
    pub const fn separator_tail(self) -> u8 {
        self.separator_tail
    }

    pub const fn has_canonical_crlf(self) -> bool {
        self.separator_tail == b'\n'
    }
}

/// Validated, borrowed view of a retail startup text table.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TextResource<'a> {
    bytes: &'a [u8],
    record_count: usize,
}

impl<'a> TextResource<'a> {
    pub fn parse(bytes: &'a [u8]) -> Result<Self, TextResourceError> {
        if bytes.is_empty() {
            return Err(TextResourceError::Empty);
        }

        let mut at = 0;
        let mut record_count = 0usize;
        while at < bytes.len() {
            let relative_cr = bytes[at..]
                .iter()
                .position(|&byte| byte == b'\r')
                .ok_or(TextResourceError::UnterminatedLine { at })?;
            let cr = at
                .checked_add(relative_cr)
                .ok_or(TextResourceError::SizeOverflow)?;
            if cr + 1 >= bytes.len() {
                return Err(TextResourceError::MissingSeparatorTail { at: cr });
            }
            at = cr + 2;
            record_count = record_count
                .checked_add(1)
                .ok_or(TextResourceError::SizeOverflow)?;
        }

        Ok(Self {
            bytes,
            record_count,
        })
    }

    pub const fn len(self) -> usize {
        self.record_count
    }

    pub const fn is_empty(self) -> bool {
        false
    }

    pub const fn iter(self) -> TextResourceIter<'a> {
        TextResourceIter {
            remaining: self.bytes,
        }
    }
}

impl<'a> IntoIterator for TextResource<'a> {
    type Item = TextRecord<'a>;
    type IntoIter = TextResourceIter<'a>;

    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

#[derive(Debug, Clone, Copy)]
pub struct TextResourceIter<'a> {
    remaining: &'a [u8],
}

impl<'a> Iterator for TextResourceIter<'a> {
    type Item = TextRecord<'a>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.remaining.is_empty() {
            return None;
        }
        // TextResource::parse proved both the CR and its following byte.
        let cr = self
            .remaining
            .iter()
            .position(|&byte| byte == b'\r')
            .expect("validated text resource");
        let record = TextRecord {
            bytes: &self.remaining[..cr],
            separator_tail: self.remaining[cr + 1],
        };
        self.remaining = &self.remaining[cr + 2..];
        Some(record)
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let count = self.remaining.iter().filter(|&&byte| byte == b'\r').count();
        (count, Some(count))
    }
}

impl ExactSizeIterator for TextResourceIter<'_> {}

/// Byte length of the canonical CRLF form emitted by [`encode_into`].
pub fn encoded_len(lines: &[&[u8]]) -> Result<usize, TextResourceError> {
    if lines.is_empty() {
        return Err(TextResourceError::Empty);
    }
    let mut size = 0usize;
    for (line_index, line) in lines.iter().enumerate() {
        if let Some(at) = line.iter().position(|&byte| byte == b'\r') {
            return Err(TextResourceError::CarriageReturnInLine {
                line: line_index,
                at,
            });
        }
        size = size
            .checked_add(line.len())
            .and_then(|value| value.checked_add(2))
            .ok_or(TextResourceError::SizeOverflow)?;
    }
    Ok(size)
}

/// Write the shipped canonical form: every record ends in CR LF, including
/// the final record. Retail accepts any byte in place of LF when reading.
pub fn encode_into(lines: &[&[u8]], dst: &mut [u8]) -> Result<usize, TextResourceError> {
    let need = encoded_len(lines)?;
    if dst.len() < need {
        return Err(TextResourceError::OutputTooSmall {
            need,
            have: dst.len(),
        });
    }

    let mut at = 0;
    for line in lines {
        let end = at + line.len();
        dst[at..end].copy_from_slice(line);
        dst[end] = b'\r';
        dst[end + 1] = b'\n';
        at = end + 2;
    }
    Ok(at)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    #[test]
    fn parses_shipped_crlf_records() {
        let table = TextResource::parse(b"alpha\r\nbeta value\r\n\r\n").unwrap();
        assert_eq!(table.len(), 3);
        let records = table.into_iter().collect::<std::vec::Vec<_>>();
        assert_eq!(records[0].bytes(), b"alpha");
        assert_eq!(records[1].bytes(), b"beta value");
        assert_eq!(records[2].bytes(), b"");
        assert!(records.iter().all(|record| record.has_canonical_crlf()));
    }

    #[test]
    fn preserves_the_unchecked_byte_after_cr() {
        let table = TextResource::parse(b"first\rXsecond\r\0").unwrap();
        let records = table.into_iter().collect::<std::vec::Vec<_>>();
        assert_eq!(records[0].bytes(), b"first");
        assert_eq!(records[0].separator_tail(), b'X');
        assert_eq!(records[1].bytes(), b"second");
        assert_eq!(records[1].separator_tail(), 0);
    }

    #[test]
    fn rejects_inputs_that_make_retail_walk_out_of_bounds() {
        assert_eq!(TextResource::parse(b""), Err(TextResourceError::Empty));
        assert_eq!(
            TextResource::parse(b"no terminator"),
            Err(TextResourceError::UnterminatedLine { at: 0 })
        );
        assert_eq!(
            TextResource::parse(b"line\r"),
            Err(TextResourceError::MissingSeparatorTail { at: 4 })
        );
        assert_eq!(
            TextResource::parse(b"one\r\ntwo"),
            Err(TextResourceError::UnterminatedLine { at: 5 })
        );
    }

    #[test]
    fn canonical_writer_round_trips_and_checks_input() {
        let lines: &[&[u8]] = &[b"one", b"", b"three"];
        let mut output = vec![0xcc; encoded_len(lines).unwrap()];
        assert_eq!(encode_into(lines, &mut output).unwrap(), output.len());
        assert_eq!(output, b"one\r\n\r\nthree\r\n");
        assert_eq!(
            TextResource::parse(&output)
                .unwrap()
                .into_iter()
                .map(TextRecord::bytes)
                .collect::<std::vec::Vec<_>>(),
            lines
        );
        assert_eq!(
            encode_into(lines, &mut output[..4]),
            Err(TextResourceError::OutputTooSmall { need: 14, have: 4 })
        );
        assert_eq!(
            encoded_len(&[b"bad\rline"]),
            Err(TextResourceError::CarriageReturnInLine { line: 0, at: 3 })
        );
        assert_eq!(encoded_len(&[]), Err(TextResourceError::Empty));
    }
}
