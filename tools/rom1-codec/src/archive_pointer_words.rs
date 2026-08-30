//! `CTextPointerVector::Serialize` at `0x069390`.
//!
//! The game-owned vector uses MFC `CArchive::WriteCount`/`ReadCount`, followed
//! by `count * 4` bytes copied directly from its pointer array. Consequently
//! this is a process-address snapshot, not a portable string table:
//!
//! ```text
//! count < 0xffff: u16 count
//! otherwise:      u16 0xffff, u32 count
//! u32 pointer_word[count]
//! ```

use core::fmt;

const EXTENDED_COUNT: u16 = 0xffff;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ArchivePointerWordsError {
    Truncated { at: usize, need: usize, have: usize },
    SizeOverflow,
    OutputTooSmall { need: usize, have: usize },
}

impl fmt::Display for ArchivePointerWordsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            ArchivePointerWordsError::Truncated { at, need, have } => {
                write!(f, "archive has {have} byte(s) at offset {at}; need {need}")
            }
            ArchivePointerWordsError::SizeOverflow => {
                write!(f, "archive pointer-word table exceeds addressable size")
            }
            ArchivePointerWordsError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
        }
    }
}

impl core::error::Error for ArchivePointerWordsError {}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ArchivePointerWords<'a> {
    words: &'a [u8],
    trailing: &'a [u8],
}

impl<'a> ArchivePointerWords<'a> {
    pub const fn len(self) -> usize {
        self.words.len() / 4
    }

    pub const fn is_empty(self) -> bool {
        self.words.is_empty()
    }

    pub fn get(self, index: usize) -> Option<u32> {
        if index >= self.len() {
            return None;
        }
        let at = index * 4;
        Some(u32::from_le_bytes([
            self.words[at],
            self.words[at + 1],
            self.words[at + 2],
            self.words[at + 3],
        ]))
    }

    pub const fn raw_words(self) -> &'a [u8] {
        self.words
    }

    pub const fn trailing(self) -> &'a [u8] {
        self.trailing
    }

    pub const fn iter(self) -> ArchivePointerWordIter<'a> {
        ArchivePointerWordIter {
            table: self,
            index: 0,
        }
    }
}

impl<'a> IntoIterator for ArchivePointerWords<'a> {
    type Item = u32;
    type IntoIter = ArchivePointerWordIter<'a>;

    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

#[derive(Debug, Clone, Copy)]
pub struct ArchivePointerWordIter<'a> {
    table: ArchivePointerWords<'a>,
    index: usize,
}

impl Iterator for ArchivePointerWordIter<'_> {
    type Item = u32;

    fn next(&mut self) -> Option<Self::Item> {
        let value = self.table.get(self.index)?;
        self.index += 1;
        Some(value)
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        let remaining = self.table.len() - self.index;
        (remaining, Some(remaining))
    }
}

impl ExactSizeIterator for ArchivePointerWordIter<'_> {}

fn take(src: &[u8], at: usize, need: usize) -> Result<&[u8], ArchivePointerWordsError> {
    src.get(at..at.saturating_add(need))
        .ok_or(ArchivePointerWordsError::Truncated {
            at,
            need,
            have: src.len().saturating_sub(at),
        })
}

/// Parse one vector serializer payload and retain any following archive bytes.
pub fn parse(src: &[u8]) -> Result<ArchivePointerWords<'_>, ArchivePointerWordsError> {
    let count16 = take(src, 0, 2)?;
    let short = u16::from_le_bytes([count16[0], count16[1]]);
    let (count, words_at) = if short != EXTENDED_COUNT {
        (usize::from(short), 2usize)
    } else {
        let count32 = take(src, 2, 4)?;
        (
            u32::from_le_bytes([count32[0], count32[1], count32[2], count32[3]]) as usize,
            6usize,
        )
    };
    let word_bytes = count
        .checked_mul(4)
        .ok_or(ArchivePointerWordsError::SizeOverflow)?;
    let end = words_at
        .checked_add(word_bytes)
        .ok_or(ArchivePointerWordsError::SizeOverflow)?;
    take(src, words_at, word_bytes)?;
    Ok(ArchivePointerWords {
        words: &src[words_at..end],
        trailing: &src[end..],
    })
}

pub fn encoded_len(word_count: usize) -> Result<usize, ArchivePointerWordsError> {
    let prefix = if word_count < usize::from(EXTENDED_COUNT) {
        2usize
    } else {
        u32::try_from(word_count).map_err(|_| ArchivePointerWordsError::SizeOverflow)?;
        6usize
    };
    prefix
        .checked_add(
            word_count
                .checked_mul(4)
                .ok_or(ArchivePointerWordsError::SizeOverflow)?,
        )
        .ok_or(ArchivePointerWordsError::SizeOverflow)
}

/// Write the exact MFC count prefix and raw little-endian 32-bit words.
pub fn encode_into(words: &[u32], dst: &mut [u8]) -> Result<usize, ArchivePointerWordsError> {
    let need = encoded_len(words.len())?;
    if dst.len() < need {
        return Err(ArchivePointerWordsError::OutputTooSmall {
            need,
            have: dst.len(),
        });
    }
    let words_at = if words.len() < usize::from(EXTENDED_COUNT) {
        dst[..2].copy_from_slice(&(words.len() as u16).to_le_bytes());
        2usize
    } else {
        dst[..2].copy_from_slice(&EXTENDED_COUNT.to_le_bytes());
        dst[2..6].copy_from_slice(
            &u32::try_from(words.len())
                .map_err(|_| ArchivePointerWordsError::SizeOverflow)?
                .to_le_bytes(),
        );
        6usize
    };
    for (slot, word) in dst[words_at..need].chunks_exact_mut(4).zip(words) {
        slot.copy_from_slice(&word.to_le_bytes());
    }
    Ok(need)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    #[test]
    fn short_count_and_raw_words_round_trip() {
        let words = [0, 0x1234_5678, 0xffff_ffff];
        let mut bytes = vec![0; encoded_len(words.len()).unwrap()];
        assert_eq!(encode_into(&words, &mut bytes).unwrap(), 14);
        assert_eq!(&bytes[..2], &[3, 0]);
        let parsed = parse(&bytes).unwrap();
        assert_eq!(parsed.into_iter().collect::<std::vec::Vec<_>>(), words);
        assert!(parsed.trailing().is_empty());
    }

    #[test]
    fn extended_marker_uses_a_little_endian_dword_count() {
        let bytes = [0xff, 0xff, 1, 0, 0, 0, 0x78, 0x56, 0x34, 0x12, 0xaa];
        let parsed = parse(&bytes).unwrap();
        assert_eq!(parsed.len(), 1);
        assert_eq!(parsed.get(0), Some(0x1234_5678));
        assert_eq!(parsed.trailing(), [0xaa]);
    }

    #[test]
    fn empty_vector_is_a_zero_word_count() {
        let parsed = parse(&[0, 0]).unwrap();
        assert!(parsed.is_empty());
        assert_eq!(parsed.raw_words(), []);
    }

    #[test]
    fn truncated_prefix_and_word_array_fail_closed() {
        assert_eq!(
            parse(&[0xff]),
            Err(ArchivePointerWordsError::Truncated {
                at: 0,
                need: 2,
                have: 1,
            })
        );
        assert_eq!(
            parse(&[0xff, 0xff, 1, 0]),
            Err(ArchivePointerWordsError::Truncated {
                at: 2,
                need: 4,
                have: 2,
            })
        );
        assert_eq!(
            parse(&[2, 0, 1, 0, 0, 0]),
            Err(ArchivePointerWordsError::Truncated {
                at: 2,
                need: 8,
                have: 4,
            })
        );
    }
}
