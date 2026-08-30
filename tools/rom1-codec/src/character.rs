//! Character (`.chr`) disk envelope produced at `0x0cf4f0` and consumed by
//! the packet reader at `0x0cf8b8`.
//!
//! ```text
//! u32 metadata[4]
//! u8  word_rle[]
//! u8  zero_pad[compressed_size & 1]
//! ```
//!
//! The four metadata words come from four non-contiguous character fields;
//! their semantic names are not yet proven. Retail stores the whole file as
//! words in its packet header, so an odd physical trailing byte is ignored on
//! load. The writer's own odd-byte padding is always zero.

use core::fmt;

pub const METADATA_SIZE: usize = 16;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CharacterEnvelopeError {
    TruncatedMetadata { have: usize },
    SizeOverflow,
    OutputTooSmall { need: usize, have: usize },
}

impl fmt::Display for CharacterEnvelopeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            CharacterEnvelopeError::TruncatedMetadata { have } => {
                write!(f, "character file has {have} complete byte(s); need 16")
            }
            CharacterEnvelopeError::SizeOverflow => {
                write!(f, "character envelope exceeds addressable size")
            }
            CharacterEnvelopeError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
        }
    }
}

impl core::error::Error for CharacterEnvelopeError {}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CharacterEnvelope<'a> {
    metadata: &'a [u8],
    word_rle: &'a [u8],
    ignored_trailing: &'a [u8],
}

impl<'a> CharacterEnvelope<'a> {
    pub const fn metadata(self) -> &'a [u8] {
        self.metadata
    }

    pub fn metadata_word(self, index: usize) -> Option<u32> {
        if index >= 4 {
            return None;
        }
        let at = index * 4;
        Some(u32::from_le_bytes([
            self.metadata[at],
            self.metadata[at + 1],
            self.metadata[at + 2],
            self.metadata[at + 3],
        ]))
    }

    /// Word-RLE extent passed to retail, including the writer's possible
    /// one-byte zero padding.
    pub const fn word_rle(self) -> &'a [u8] {
        self.word_rle
    }

    /// At most one physical byte, dropped by retail's `file_length >> 1`.
    pub const fn ignored_trailing(self) -> &'a [u8] {
        self.ignored_trailing
    }
}

/// Parse the disk file with the same even-byte truncation as its retail caller.
pub fn parse(src: &[u8]) -> Result<CharacterEnvelope<'_>, CharacterEnvelopeError> {
    let consumed = src.len() & !1usize;
    if consumed < METADATA_SIZE {
        return Err(CharacterEnvelopeError::TruncatedMetadata { have: consumed });
    }
    Ok(CharacterEnvelope {
        metadata: &src[..METADATA_SIZE],
        word_rle: &src[METADATA_SIZE..consumed],
        ignored_trailing: &src[consumed..],
    })
}

pub fn encoded_len(word_rle_len: usize) -> Result<usize, CharacterEnvelopeError> {
    let padded = word_rle_len
        .checked_add(word_rle_len & 1)
        .ok_or(CharacterEnvelopeError::SizeOverflow)?;
    METADATA_SIZE
        .checked_add(padded)
        .ok_or(CharacterEnvelopeError::SizeOverflow)
}

/// Write the exact disk payload: four little-endian metadata words, the
/// compressed stream, and a zero byte only when the stream length is odd.
pub fn encode_into(
    metadata: [u32; 4],
    word_rle: &[u8],
    dst: &mut [u8],
) -> Result<usize, CharacterEnvelopeError> {
    let need = encoded_len(word_rle.len())?;
    if dst.len() < need {
        return Err(CharacterEnvelopeError::OutputTooSmall {
            need,
            have: dst.len(),
        });
    }
    for (slot, word) in dst[..METADATA_SIZE].chunks_exact_mut(4).zip(metadata) {
        slot.copy_from_slice(&word.to_le_bytes());
    }
    let end = METADATA_SIZE + word_rle.len();
    dst[METADATA_SIZE..end].copy_from_slice(word_rle);
    if end < need {
        dst[end] = 0;
    }
    Ok(need)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    #[test]
    fn even_stream_round_trips_without_padding() {
        let metadata = [0, 1, 0x1234_5678, 0xffff_ffff];
        let stream = [2, 0, 0, 0, 0x82, 7, 0, 0];
        let mut bytes = vec![0xcc; encoded_len(stream.len()).unwrap()];
        assert_eq!(encode_into(metadata, &stream, &mut bytes).unwrap(), 24);
        let parsed = parse(&bytes).unwrap();
        assert_eq!(parsed.word_rle(), stream);
        assert_eq!(parsed.ignored_trailing(), []);
        for (index, expected) in metadata.into_iter().enumerate() {
            assert_eq!(parsed.metadata_word(index), Some(expected));
        }
        assert_eq!(parsed.metadata_word(4), None);
    }

    #[test]
    fn odd_stream_receives_one_zero_byte() {
        let stream = [1, 0, 0, 0, 1, 0x34, 0x12];
        let mut bytes = vec![0xcc; encoded_len(stream.len()).unwrap()];
        assert_eq!(encode_into([1, 2, 3, 4], &stream, &mut bytes).unwrap(), 24);
        let parsed = parse(&bytes).unwrap();
        assert_eq!(&parsed.word_rle()[..stream.len()], stream);
        assert_eq!(parsed.word_rle()[stream.len()], 0);
    }

    #[test]
    fn physical_odd_tail_is_ignored_like_retail_file_loader() {
        let mut bytes = [0u8; 19];
        bytes[16..].copy_from_slice(&[0xaa, 0xbb, 0xcc]);
        let parsed = parse(&bytes).unwrap();
        assert_eq!(parsed.word_rle(), [0xaa, 0xbb]);
        assert_eq!(parsed.ignored_trailing(), [0xcc]);
    }

    #[test]
    fn short_metadata_and_small_output_fail_closed() {
        assert_eq!(
            parse(&[0; 15]),
            Err(CharacterEnvelopeError::TruncatedMetadata { have: 14 })
        );
        assert_eq!(
            encode_into([0; 4], &[1], &mut [0; 17]),
            Err(CharacterEnvelopeError::OutputTooSmall { need: 18, have: 17 })
        );
    }
}
