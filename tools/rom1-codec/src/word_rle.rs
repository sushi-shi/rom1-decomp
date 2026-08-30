//! The word-RLE stream used by save games and character files.
//!
//! Transcribed independently from the retail encoder at `0x11f130`, decoder
//! at `0x11f1e0`, and token helpers at `0x127040..0x1272f7`.
//!
//! ```text
//! dword decoded_word_count
//! token...
//!
//! token & 0x80 != 0  => repeat (token & 0x7f) times; one u16 payload
//! token & 0x80 == 0  => copy token u16 payloads literally
//! ```
//!
//! The encoder has one observable retail quirk: it reads `words[len]` before
//! checking the logical boundary. [`encode_into`] therefore takes that padded
//! lookahead word explicitly. Equal-to-last selects a one-word repeat token;
//! any other value selects a one-word literal token.

use core::fmt;

use crate::Sink;

const HEADER_SIZE: usize = 4;
const FLAG_REPEAT: u8 = 0x80;
const MAX_RUN: usize = 0x7f;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WordRleError {
    WordCountTooLarge,
    StreamTooShort { at: usize, need: usize },
    OutputTooSmall { need: usize, have: usize },
    DecodedWordCountMismatch { declared: usize, decoded: usize },
}

impl fmt::Display for WordRleError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            WordRleError::WordCountTooLarge => write!(f, "word count does not fit a dword"),
            WordRleError::StreamTooShort { at, need } => {
                write!(f, "stream ends at byte {at}; token needs {need} byte(s)")
            }
            WordRleError::OutputTooSmall { need, have } => {
                write!(f, "output holds {have} word(s), need {need}")
            }
            WordRleError::DecodedWordCountMismatch { declared, decoded } => {
                write!(f, "header declares {declared} word(s), decoded {decoded}")
            }
        }
    }
}

impl core::error::Error for WordRleError {}

fn word_at(words: &[u16], lookahead: u16, index: usize) -> u16 {
    words.get(index).copied().unwrap_or(lookahead)
}

fn encode(words: &[u16], lookahead: u16, sink: &mut Sink<'_>) -> Result<(), WordRleError> {
    let count = u32::try_from(words.len()).map_err(|_| WordRleError::WordCountTooLarge)?;
    if !sink.extend(&count.to_le_bytes()) {
        return Err(WordRleError::OutputTooSmall {
            need: HEADER_SIZE,
            have: sink.len(),
        });
    }

    let mut index = 0usize;
    while index < words.len() {
        if word_at(words, lookahead, index) == word_at(words, lookahead, index + 1) {
            let mut run = 1usize;
            let mut cursor = index + 1;
            while word_at(words, lookahead, cursor - 1) == word_at(words, lookahead, cursor)
                && run < MAX_RUN
                && index + run < words.len()
            {
                run += 1;
                cursor += 1;
            }
            let value = word_at(words, lookahead, cursor - 1).to_le_bytes();
            if !sink.push(FLAG_REPEAT | u8::try_from(run).unwrap_or(MAX_RUN as u8))
                || !sink.extend(&value)
            {
                return Err(WordRleError::OutputTooSmall {
                    need: 0,
                    have: sink.len(),
                });
            }
            index += run;
        } else {
            let mut count = 1usize;
            let mut cursor = index + 1;
            while word_at(words, lookahead, cursor - 1) != word_at(words, lookahead, cursor)
                && count < MAX_RUN
                && index + count < words.len()
            {
                count += 1;
                cursor += 1;
            }
            if index + count == words.len() {
                count += 1;
            }
            let literals = count - 1;
            if !sink.push(u8::try_from(literals).unwrap_or(MAX_RUN as u8)) {
                return Err(WordRleError::OutputTooSmall {
                    need: 0,
                    have: sink.len(),
                });
            }
            for &word in &words[index..index + literals] {
                if !sink.extend(&word.to_le_bytes()) {
                    return Err(WordRleError::OutputTooSmall {
                        need: 0,
                        have: sink.len(),
                    });
                }
            }
            index += literals;
        }
    }
    Ok(())
}

/// Exact encoded length for [`encode_into`].
pub fn encoded_len(words: &[u16], lookahead: u16) -> Result<usize, WordRleError> {
    let mut sink = Sink::Count(0);
    encode(words, lookahead, &mut sink)?;
    Ok(sink.len())
}

/// Encode the retail stream into `dst`, including its 4-byte word-count header.
pub fn encode_into(words: &[u16], lookahead: u16, dst: &mut [u8]) -> Result<usize, WordRleError> {
    let need = encoded_len(words, lookahead)?;
    if dst.len() < need {
        return Err(WordRleError::OutputTooSmall {
            need,
            have: dst.len(),
        });
    }
    let mut sink = Sink::Write { bytes: dst, at: 0 };
    encode(words, lookahead, &mut sink)?;
    Ok(sink.len())
}

/// Read the decoded word count without walking the token stream.
pub fn decoded_word_count(src: &[u8]) -> Result<usize, WordRleError> {
    let header = src.get(..HEADER_SIZE).ok_or(WordRleError::StreamTooShort {
        at: src.len(),
        need: HEADER_SIZE,
    })?;
    Ok(u32::from_le_bytes([header[0], header[1], header[2], header[3]]) as usize)
}

/// Decode every token in `src` into `dst` and return the consumed byte count.
pub fn decode_into(src: &[u8], dst: &mut [u16]) -> Result<usize, WordRleError> {
    let declared = decoded_word_count(src)?;
    if dst.len() < declared {
        return Err(WordRleError::OutputTooSmall {
            need: declared,
            have: dst.len(),
        });
    }

    let mut input = HEADER_SIZE;
    let mut output = 0usize;
    while input < src.len() {
        let token = src[input];
        if token & FLAG_REPEAT != 0 {
            let run = usize::from(token & !FLAG_REPEAT);
            let payload = src
                .get(input + 1..input + 3)
                .ok_or(WordRleError::StreamTooShort { at: input, need: 3 })?;
            if output + run > dst.len() {
                return Err(WordRleError::OutputTooSmall {
                    need: output + run,
                    have: dst.len(),
                });
            }
            let value = u16::from_le_bytes([payload[0], payload[1]]);
            dst[output..output + run].fill(value);
            output += run;
            input += 3;
        } else {
            let run = usize::from(token);
            let bytes = run * 2;
            let payload =
                src.get(input + 1..input + 1 + bytes)
                    .ok_or(WordRleError::StreamTooShort {
                        at: input,
                        need: 1 + bytes,
                    })?;
            if output + run > dst.len() {
                return Err(WordRleError::OutputTooSmall {
                    need: output + run,
                    have: dst.len(),
                });
            }
            for (slot, pair) in dst[output..output + run]
                .iter_mut()
                .zip(payload.chunks_exact(2))
            {
                *slot = u16::from_le_bytes([pair[0], pair[1]]);
            }
            output += run;
            input += 1 + bytes;
        }
    }

    if output != declared {
        return Err(WordRleError::DecodedWordCountMismatch {
            declared,
            decoded: output,
        });
    }
    Ok(input)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    fn round_trip(words: &[u16], lookahead: u16) -> std::vec::Vec<u8> {
        let mut encoded = vec![0; encoded_len(words, lookahead).unwrap()];
        let used = encode_into(words, lookahead, &mut encoded).unwrap();
        assert_eq!(used, encoded.len());
        let mut decoded = vec![0; words.len()];
        assert_eq!(decode_into(&encoded, &mut decoded).unwrap(), encoded.len());
        assert_eq!(decoded, words);
        encoded
    }

    #[test]
    fn empty_stream_is_only_the_count() {
        assert_eq!(round_trip(&[], 0x1234), [0, 0, 0, 0]);
    }

    #[test]
    fn final_lookahead_selects_the_retail_token_class() {
        assert_eq!(round_trip(&[0x1234], 0), [1, 0, 0, 0, 1, 0x34, 0x12]);
        assert_eq!(
            round_trip(&[0x1234], 0x1234),
            [1, 0, 0, 0, 0x81, 0x34, 0x12]
        );
    }

    #[test]
    fn mixed_repeat_and_literal_tokens_match_retail_grammar() {
        assert_eq!(
            round_trip(&[1, 1, 1, 2, 3, 4, 4], 0),
            [7, 0, 0, 0, 0x83, 1, 0, 2, 2, 0, 3, 0, 0x82, 4, 0]
        );
    }

    #[test]
    fn run_caps_match_the_byte_sized_retail_counter() {
        let repeats = vec![7; 130];
        let encoded = round_trip(&repeats, 7);
        assert_eq!(&encoded[4..], &[0xff, 7, 0, 0x83, 7, 0]);

        let literals: std::vec::Vec<u16> = (0..130).collect();
        let encoded = round_trip(&literals, 0xffff);
        assert_eq!(encoded[4], 126);
        assert_eq!(encoded[4 + 1 + 126 * 2], 4);
    }

    #[test]
    fn malformed_streams_fail_closed() {
        assert_eq!(
            decode_into(&[1, 0, 0, 0, 0x81], &mut [0]),
            Err(WordRleError::StreamTooShort { at: 4, need: 3 })
        );
        assert_eq!(
            decode_into(&[2, 0, 0, 0, 1, 9, 0], &mut [0, 0]),
            Err(WordRleError::DecodedWordCountMismatch {
                declared: 2,
                decoded: 1
            })
        );
    }
}
