//! Save-game envelope written at `0x0cee6f` and read at `0x0cf1ee`.
//!
//! ```text
//! u32 magic                  // 0x26677341 (bytes `Asg&`)
//! u32 declared_file_size     // backpatched by the writer; ignored by reader
//! u32 version                // writer: 0x0bad0002
//! u32 compressed_byte_count
//! u8  word_rle[compressed_byte_count]
//! u8  server_description[256] // optional writer-only trailer
//! ```
//!
//! Retail accepts versions using a signed `version >= 0x0bad0002` comparison
//! and does not compare `declared_file_size` with either the compressed extent
//! or the physical file length. The safe parser preserves those behaviors but
//! rejects a compressed extent outside the supplied slice.

use core::fmt;

pub const MAGIC: u32 = 0x2667_7341;
pub const CURRENT_VERSION: u32 = 0x0bad_0002;
pub const HEADER_SIZE: usize = 16;
pub const SERVER_DESCRIPTION_SIZE: usize = 256;
pub const SERVER_DESCRIPTION_TEXT: &[u8] = b"Server Multiplayer save file.";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SaveGameError {
    Truncated { at: usize, need: usize, have: usize },
    InvalidMagic { found: u32 },
    OutdatedVersion { found: u32 },
    SizeOverflow,
    OutputTooSmall { need: usize, have: usize },
}

impl fmt::Display for SaveGameError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            SaveGameError::Truncated { at, need, have } => {
                write!(f, "save has {have} byte(s) at offset {at}; need {need}")
            }
            SaveGameError::InvalidMagic { found } => {
                write!(f, "invalid save magic 0x{found:08x}")
            }
            SaveGameError::OutdatedVersion { found } => {
                write!(f, "outdated save version 0x{found:08x}")
            }
            SaveGameError::SizeOverflow => write!(f, "save envelope exceeds a retail dword"),
            SaveGameError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
        }
    }
}

impl core::error::Error for SaveGameError {}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SaveGameEnvelope<'a> {
    declared_file_size: u32,
    version: u32,
    compressed: &'a [u8],
    trailing: &'a [u8],
}

impl<'a> SaveGameEnvelope<'a> {
    pub const fn declared_file_size(self) -> u32 {
        self.declared_file_size
    }

    pub const fn version(self) -> u32 {
        self.version
    }

    pub const fn compressed(self) -> &'a [u8] {
        self.compressed
    }

    /// Bytes after the compressed extent. Retail's writer uses either none or
    /// a 256-byte server-description record; retail's reader ignores all of it.
    pub const fn trailing(self) -> &'a [u8] {
        self.trailing
    }

    pub fn declared_file_size_matches(self, physical_size: usize) -> bool {
        usize::try_from(self.declared_file_size) == Ok(physical_size)
    }

    pub fn has_canonical_server_description(self) -> bool {
        if self.trailing.len() != SERVER_DESCRIPTION_SIZE {
            return false;
        }
        let text_end = SERVER_DESCRIPTION_TEXT.len();
        self.trailing[..text_end] == *SERVER_DESCRIPTION_TEXT
            && self.trailing[text_end..].iter().all(|&byte| byte == 0)
    }
}

fn dword(src: &[u8], at: usize) -> Result<u32, SaveGameError> {
    let bytes = src.get(at..at + 4).ok_or(SaveGameError::Truncated {
        at,
        need: 4,
        have: src.len().saturating_sub(at),
    })?;
    Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
}

/// Parse exactly as the retail reader validates the envelope.
pub fn parse(src: &[u8]) -> Result<SaveGameEnvelope<'_>, SaveGameError> {
    let magic = dword(src, 0)?;
    if magic != MAGIC {
        return Err(SaveGameError::InvalidMagic { found: magic });
    }
    let declared_file_size = dword(src, 4)?;
    let version = dword(src, 8)?;
    if (version as i32) < (CURRENT_VERSION as i32) {
        return Err(SaveGameError::OutdatedVersion { found: version });
    }
    let compressed_len =
        usize::try_from(dword(src, 12)?).map_err(|_| SaveGameError::SizeOverflow)?;
    let end = HEADER_SIZE
        .checked_add(compressed_len)
        .ok_or(SaveGameError::SizeOverflow)?;
    src.get(HEADER_SIZE..end).ok_or(SaveGameError::Truncated {
        at: HEADER_SIZE,
        need: compressed_len,
        have: src.len().saturating_sub(HEADER_SIZE),
    })?;
    Ok(SaveGameEnvelope {
        declared_file_size,
        version,
        compressed: &src[HEADER_SIZE..end],
        trailing: &src[end..],
    })
}

pub fn encoded_len(
    compressed_len: usize,
    server_multiplayer: bool,
) -> Result<usize, SaveGameError> {
    u32::try_from(compressed_len).map_err(|_| SaveGameError::SizeOverflow)?;
    let trailer = if server_multiplayer {
        SERVER_DESCRIPTION_SIZE
    } else {
        0
    };
    let total = HEADER_SIZE
        .checked_add(compressed_len)
        .and_then(|size| size.checked_add(trailer))
        .ok_or(SaveGameError::SizeOverflow)?;
    u32::try_from(total).map_err(|_| SaveGameError::SizeOverflow)?;
    Ok(total)
}

/// Write the canonical current-version envelope produced by retail.
pub fn encode_into(
    compressed: &[u8],
    server_multiplayer: bool,
    dst: &mut [u8],
) -> Result<usize, SaveGameError> {
    let need = encoded_len(compressed.len(), server_multiplayer)?;
    if dst.len() < need {
        return Err(SaveGameError::OutputTooSmall {
            need,
            have: dst.len(),
        });
    }
    dst[..need].fill(0);
    dst[0..4].copy_from_slice(&MAGIC.to_le_bytes());
    dst[4..8].copy_from_slice(&(need as u32).to_le_bytes());
    dst[8..12].copy_from_slice(&CURRENT_VERSION.to_le_bytes());
    dst[12..16].copy_from_slice(&(compressed.len() as u32).to_le_bytes());
    dst[HEADER_SIZE..HEADER_SIZE + compressed.len()].copy_from_slice(compressed);
    if server_multiplayer {
        let at = HEADER_SIZE + compressed.len();
        dst[at..at + SERVER_DESCRIPTION_TEXT.len()].copy_from_slice(SERVER_DESCRIPTION_TEXT);
    }
    Ok(need)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    #[test]
    fn canonical_single_player_envelope_round_trips() {
        let compressed = [3, 0, 0, 0, 0x83, 7, 0];
        let mut bytes = vec![0xcc; encoded_len(compressed.len(), false).unwrap()];
        assert_eq!(encode_into(&compressed, false, &mut bytes).unwrap(), 23);
        assert_eq!(&bytes[..4], b"Asg&");
        let parsed = parse(&bytes).unwrap();
        assert_eq!(parsed.declared_file_size(), 23);
        assert_eq!(parsed.version(), CURRENT_VERSION);
        assert_eq!(parsed.compressed(), compressed);
        assert!(parsed.trailing().is_empty());
        assert!(parsed.declared_file_size_matches(bytes.len()));
    }

    #[test]
    fn server_writer_appends_exact_fixed_record() {
        let mut bytes = vec![0xcc; encoded_len(1, true).unwrap()];
        encode_into(&[0], true, &mut bytes).unwrap();
        let parsed = parse(&bytes).unwrap();
        assert_eq!(parsed.trailing().len(), SERVER_DESCRIPTION_SIZE);
        assert!(parsed.has_canonical_server_description());
    }

    #[test]
    fn reader_ignores_declared_size_and_arbitrary_trailing_bytes() {
        let mut bytes = [0u8; 19];
        bytes[0..4].copy_from_slice(&MAGIC.to_le_bytes());
        bytes[4..8].copy_from_slice(&0xdead_beefu32.to_le_bytes());
        bytes[8..12].copy_from_slice(&CURRENT_VERSION.to_le_bytes());
        bytes[12..16].copy_from_slice(&[1, 0, 0, 0]);
        bytes[16] = 0xaa;
        bytes[17..].copy_from_slice(&[0xbb, 0xcc]);
        let parsed = parse(&bytes).unwrap();
        assert_eq!(parsed.compressed(), [0xaa]);
        assert_eq!(parsed.trailing(), [0xbb, 0xcc]);
        assert!(!parsed.declared_file_size_matches(bytes.len()));
    }

    #[test]
    fn signed_version_floor_matches_retail() {
        let mut bytes = [0u8; HEADER_SIZE];
        bytes[0..4].copy_from_slice(&MAGIC.to_le_bytes());
        bytes[8..12].copy_from_slice(&(CURRENT_VERSION - 1).to_le_bytes());
        assert_eq!(
            parse(&bytes),
            Err(SaveGameError::OutdatedVersion {
                found: CURRENT_VERSION - 1
            })
        );
        bytes[8..12].copy_from_slice(&(CURRENT_VERSION + 1).to_le_bytes());
        assert!(parse(&bytes).is_ok());
        bytes[8..12].copy_from_slice(&0x8000_0000u32.to_le_bytes());
        assert_eq!(
            parse(&bytes),
            Err(SaveGameError::OutdatedVersion { found: 0x8000_0000 })
        );
    }

    #[test]
    fn invalid_magic_truncated_payload_and_small_output_fail_closed() {
        assert_eq!(
            parse(&[0, 0, 0, 0]),
            Err(SaveGameError::InvalidMagic { found: 0 })
        );
        let mut bytes = [0u8; HEADER_SIZE];
        bytes[0..4].copy_from_slice(&MAGIC.to_le_bytes());
        bytes[8..12].copy_from_slice(&CURRENT_VERSION.to_le_bytes());
        bytes[12..16].copy_from_slice(&1u32.to_le_bytes());
        assert_eq!(
            parse(&bytes),
            Err(SaveGameError::Truncated {
                at: HEADER_SIZE,
                need: 1,
                have: 0
            })
        );
        assert_eq!(
            encode_into(&[1, 2], false, &mut [0; 17]),
            Err(SaveGameError::OutputTooSmall { need: 18, have: 17 })
        );
    }
}
