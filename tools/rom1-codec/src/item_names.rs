//! Raw item-name ID table loaded by retail `LoadItemNames` at `0x068490`.
//!
//! `main\\text\\itemname.bin` has no header or terminator. Every complete
//! little-endian `u16` is an item ID; its zero-based file position selects a
//! string from the already-loaded item-name text block. Retail computes the
//! entry count with `file_length >> 1`, so one odd trailing byte is ignored.

use core::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ItemNameIdError {
    TooManyIds,
    OutputTooSmall { need: usize, have: usize },
}

impl fmt::Display for ItemNameIdError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            ItemNameIdError::TooManyIds => write!(f, "item-name ID byte size overflows usize"),
            ItemNameIdError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
        }
    }
}

impl core::error::Error for ItemNameIdError {}

/// Borrowed view of retail's headerless item-name ID table.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ItemNameIds<'a> {
    bytes: &'a [u8],
}

impl<'a> ItemNameIds<'a> {
    pub const fn new(bytes: &'a [u8]) -> Self {
        Self { bytes }
    }

    /// Number of complete IDs. This is exactly retail's `file_length >> 1`.
    pub const fn len(self) -> usize {
        self.bytes.len() / 2
    }

    pub const fn is_empty(self) -> bool {
        self.len() == 0
    }

    pub const fn has_ignored_trailing_byte(self) -> bool {
        self.bytes.len() & 1 != 0
    }

    pub fn get(self, index: usize) -> Option<u16> {
        if index >= self.len() {
            return None;
        }
        let at = index * 2;
        Some(u16::from_le_bytes([self.bytes[at], self.bytes[at + 1]]))
    }

    pub const fn consumed_bytes(self) -> usize {
        self.len() * 2
    }

    pub const fn ignored_trailing_bytes(self) -> &'a [u8] {
        let at = self.consumed_bytes();
        // `at` is derived from this slice's length and is always in bounds.
        self.bytes.split_at(at).1
    }

    pub const fn iter(self) -> ItemNameIdIter<'a> {
        ItemNameIdIter {
            table: self,
            index: 0,
        }
    }
}

impl<'a> IntoIterator for ItemNameIds<'a> {
    type Item = u16;
    type IntoIter = ItemNameIdIter<'a>;

    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

#[derive(Debug, Clone, Copy)]
pub struct ItemNameIdIter<'a> {
    table: ItemNameIds<'a>,
    index: usize,
}

impl Iterator for ItemNameIdIter<'_> {
    type Item = u16;

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

impl ExactSizeIterator for ItemNameIdIter<'_> {}

/// Exact byte length of a headerless encoded table.
pub fn encoded_len(id_count: usize) -> Result<usize, ItemNameIdError> {
    id_count.checked_mul(2).ok_or(ItemNameIdError::TooManyIds)
}

/// Write a canonical item-name ID table. Writers never emit the retail-ignored
/// odd trailing byte, but [`ItemNameIds`] preserves and reports it when read.
pub fn encode_into(ids: &[u16], dst: &mut [u8]) -> Result<usize, ItemNameIdError> {
    let need = encoded_len(ids.len())?;
    if dst.len() < need {
        return Err(ItemNameIdError::OutputTooSmall {
            need,
            have: dst.len(),
        });
    }
    for (pair, id) in dst[..need].chunks_exact_mut(2).zip(ids) {
        pair.copy_from_slice(&id.to_le_bytes());
    }
    Ok(need)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    #[test]
    fn empty_table_has_no_ids_or_tail() {
        let table = ItemNameIds::new(&[]);
        assert!(table.is_empty());
        assert_eq!(table.get(0), None);
        assert_eq!(table.ignored_trailing_bytes(), []);
    }

    #[test]
    fn ids_are_little_endian_and_positioned_by_file_order() {
        let table = ItemNameIds::new(&[0x34, 0x12, 0xcd, 0xab, 0, 0]);
        assert_eq!(table.len(), 3);
        assert_eq!(table.get(0), Some(0x1234));
        assert_eq!(table.get(1), Some(0xabcd));
        assert_eq!(table.get(2), Some(0));
        assert_eq!(table.get(3), None);
        assert_eq!(
            table.into_iter().collect::<std::vec::Vec<_>>(),
            [0x1234, 0xabcd, 0]
        );
    }

    #[test]
    fn one_odd_trailing_byte_is_ignored_like_retail() {
        let table = ItemNameIds::new(&[1, 0, 2, 0, 0xee]);
        assert_eq!(table.into_iter().collect::<std::vec::Vec<_>>(), [1, 2]);
        assert_eq!(table.consumed_bytes(), 4);
        assert!(table.has_ignored_trailing_byte());
        assert_eq!(table.ignored_trailing_bytes(), [0xee]);
    }

    #[test]
    fn canonical_writer_round_trips_and_checks_capacity() {
        let ids = [0, 1, 0x1234, 0xffff];
        let mut bytes = vec![0xcc; encoded_len(ids.len()).unwrap()];
        assert_eq!(encode_into(&ids, &mut bytes).unwrap(), 8);
        assert_eq!(
            ItemNameIds::new(&bytes)
                .into_iter()
                .collect::<std::vec::Vec<_>>(),
            ids
        );
        assert_eq!(
            encode_into(&ids, &mut bytes[..7]),
            Err(ItemNameIdError::OutputTooSmall { need: 8, have: 7 })
        );
    }
}
