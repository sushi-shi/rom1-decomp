//! Retail `.res` archive tree loaded at `0x0c9070`.
//!
//! This is the game's own container, not a Win32 compiled-resource `.res`:
//!
//! ```text
//! u32 root_tag = 0x31415926
//! u32 root_value             // first child index
//! u32 root_child_count
//! u32 root_flags
//! u32 index_offset
//! u32 record_count
//! u8  payload[]
//! Record records[record_count] // normally at index_offset
//!
//! Record = {
//!     u32 tag,
//!     u32 value,             // child index for a directory, file offset otherwise
//!     u32 child_count_or_size,
//!     u32 flags,
//!     u8  name[16],
//! }
//! ```
//!
//! Path lookup at `0x0ce7e0` first consumes the archive base name (for
//! example `main`), then walks slash- or backslash-separated records. The
//! ordinary unsorted path compares at most 15 bytes case-insensitively. A
//! sorted directory uses the executable's case-sensitive record comparator.
//! `update.lst` processing at `0x0c99f0` marks matching records with
//! [`RECORD_DISABLED`]; lookup at `0x0c92f0` returns a distinct sentinel for
//! that state, stopping fallback into an older mounted archive.

use core::{cmp::Ordering, fmt};

pub const MAGIC: u32 = 0x3141_5926;
pub const HEADER_SIZE: usize = 24;
pub const RECORD_SIZE: usize = 32;
pub const RECORD_NAME_SIZE: usize = 16;
pub const RECORD_NAME_COMPARE_SIZE: usize = 15;

pub const RECORD_CONTAINER: u32 = 0x0000_0001;
pub const RECORD_CHILDREN_SORTED: u32 = 0x0000_0010;
pub const RECORD_NAME_TRUNCATED: u32 = 0x1000_0000;
pub const RECORD_DISABLED: u32 = 0x2000_0000;
pub const RECORD_FINALIZED: u32 = 0x4000_0000;
pub const ROOT_INDEX_INLINE: u32 = 0x8000_0000;

const TRAVERSABLE_MASK: u32 = RECORD_FINALIZED | RECORD_CONTAINER;
const LOOKUP_REJECT_MASK: u32 = RECORD_FINALIZED | RECORD_CHILDREN_SORTED;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResourceArchiveError {
    Truncated {
        at: usize,
        need: usize,
        have: usize,
    },
    InvalidMagic {
        found: u32,
    },
    SizeOverflow,
    RecordOutOfBounds {
        index: u32,
        count: u32,
    },
    ChildRangeOutOfBounds {
        first: u32,
        count: u32,
        records: u32,
    },
    PayloadOutOfBounds {
        offset: u32,
        size: u32,
        archive_size: usize,
    },
}

impl fmt::Display for ResourceArchiveError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            ResourceArchiveError::Truncated { at, need, have } => {
                write!(f, "archive has {have} byte(s) at offset {at}; need {need}")
            }
            ResourceArchiveError::InvalidMagic { found } => {
                write!(f, "invalid .res magic 0x{found:08x}")
            }
            ResourceArchiveError::SizeOverflow => write!(f, ".res extent overflows usize"),
            ResourceArchiveError::RecordOutOfBounds { index, count } => {
                write!(f, "record {index} is outside the {count}-record index")
            }
            ResourceArchiveError::ChildRangeOutOfBounds {
                first,
                count,
                records,
            } => write!(
                f,
                "child range {first}..+{count} is outside the {records}-record index"
            ),
            ResourceArchiveError::PayloadOutOfBounds {
                offset,
                size,
                archive_size,
            } => write!(
                f,
                "payload {offset}..+{size} is outside the {archive_size}-byte archive"
            ),
        }
    }
}

impl core::error::Error for ResourceArchiveError {}

fn take(src: &[u8], at: usize, need: usize) -> Result<&[u8], ResourceArchiveError> {
    let end = at
        .checked_add(need)
        .ok_or(ResourceArchiveError::SizeOverflow)?;
    src.get(at..end).ok_or(ResourceArchiveError::Truncated {
        at,
        need,
        have: src.len().saturating_sub(at),
    })
}

fn dword(src: &[u8], at: usize) -> Result<u32, ResourceArchiveError> {
    let bytes = take(src, at, 4)?;
    Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RootRecord {
    value: u32,
    child_count: u32,
    flags: u32,
}

impl RootRecord {
    pub const fn value(self) -> u32 {
        self.value
    }

    pub const fn child_count(self) -> u32 {
        self.child_count
    }

    pub const fn flags(self) -> u32 {
        self.flags
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Record<'a> {
    tag: u32,
    value: u32,
    child_count_or_size: u32,
    flags: u32,
    name: &'a [u8],
}

impl<'a> Record<'a> {
    pub const fn tag(self) -> u32 {
        self.tag
    }

    pub const fn value(self) -> u32 {
        self.value
    }

    pub const fn child_count_or_size(self) -> u32 {
        self.child_count_or_size
    }

    pub const fn flags(self) -> u32 {
        self.flags
    }

    /// Name bytes through the first NUL, or all 16 bytes when none is present.
    pub fn name(self) -> &'a [u8] {
        let end = self
            .name
            .iter()
            .position(|&byte| byte == 0)
            .unwrap_or(self.name.len());
        &self.name[..end]
    }

    pub const fn raw_name(self) -> &'a [u8] {
        self.name
    }

    pub const fn is_container(self) -> bool {
        self.flags & TRAVERSABLE_MASK == RECORD_CONTAINER
    }

    pub const fn is_disabled(self) -> bool {
        self.flags & RECORD_DISABLED != 0
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Resource<'a> {
    offset: u32,
    flags: u32,
    bytes: &'a [u8],
}

impl<'a> Resource<'a> {
    pub const fn offset(self) -> u32 {
        self.offset
    }

    pub const fn flags(self) -> u32 {
        self.flags
    }

    pub const fn bytes(self) -> &'a [u8] {
        self.bytes
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Lookup<'a> {
    Missing,
    Disabled,
    Found(Resource<'a>),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ResourceArchive<'a> {
    src: &'a [u8],
    root: RootRecord,
    recorded_index_offset: u32,
    index_offset: usize,
    record_count: u32,
}

impl<'a> ResourceArchive<'a> {
    pub fn parse(src: &'a [u8]) -> Result<Self, ResourceArchiveError> {
        let magic = dword(src, 0)?;
        if magic != MAGIC {
            return Err(ResourceArchiveError::InvalidMagic { found: magic });
        }
        let root = RootRecord {
            value: dword(src, 4)?,
            child_count: dword(src, 8)?,
            flags: dword(src, 12)?,
        };
        let recorded_index_offset = dword(src, 16)?;
        let record_count = dword(src, 20)?;
        let index_offset = if root.flags & ROOT_INDEX_INLINE != 0 {
            HEADER_SIZE
        } else {
            usize::try_from(recorded_index_offset)
                .map_err(|_| ResourceArchiveError::SizeOverflow)?
        };
        let index_size = usize::try_from(record_count)
            .map_err(|_| ResourceArchiveError::SizeOverflow)?
            .checked_mul(RECORD_SIZE)
            .ok_or(ResourceArchiveError::SizeOverflow)?;
        take(src, index_offset, index_size)?;

        Ok(Self {
            src,
            root,
            recorded_index_offset,
            index_offset,
            record_count,
        })
    }

    pub const fn root(self) -> RootRecord {
        self.root
    }

    pub const fn recorded_index_offset(self) -> u32 {
        self.recorded_index_offset
    }

    pub const fn index_offset(self) -> usize {
        self.index_offset
    }

    pub const fn record_count(self) -> u32 {
        self.record_count
    }

    pub fn record(self, index: u32) -> Result<Record<'a>, ResourceArchiveError> {
        if index >= self.record_count {
            return Err(ResourceArchiveError::RecordOutOfBounds {
                index,
                count: self.record_count,
            });
        }
        let at = self
            .index_offset
            .checked_add(
                usize::try_from(index)
                    .map_err(|_| ResourceArchiveError::SizeOverflow)?
                    .checked_mul(RECORD_SIZE)
                    .ok_or(ResourceArchiveError::SizeOverflow)?,
            )
            .ok_or(ResourceArchiveError::SizeOverflow)?;
        Ok(Record {
            tag: dword(self.src, at)?,
            value: dword(self.src, at + 4)?,
            child_count_or_size: dword(self.src, at + 8)?,
            flags: dword(self.src, at + 12)?,
            name: take(self.src, at + 16, RECORD_NAME_SIZE)?,
        })
    }

    fn checked_children(self, first: u32, count: u32) -> Result<(), ResourceArchiveError> {
        if first
            .checked_add(count)
            .is_none_or(|end| end > self.record_count)
        {
            return Err(ResourceArchiveError::ChildRangeOutOfBounds {
                first,
                count,
                records: self.record_count,
            });
        }
        Ok(())
    }

    fn find_child(
        self,
        first: u32,
        count: u32,
        flags: u32,
        name: &[u8],
    ) -> Result<Option<Record<'a>>, ResourceArchiveError> {
        self.checked_children(first, count)?;
        if flags & RECORD_CHILDREN_SORTED == 0 || count == 0 {
            for index in 0..count {
                let record = self.record(first + index)?;
                if equal_name_15_case_insensitive(name, record.raw_name()) {
                    return Ok(Some(record));
                }
            }
            return Ok(None);
        }

        let probe_len = name.len().min(RECORD_NAME_COMPARE_SIZE);
        let probe = &name[..probe_len];
        let mut low = 0;
        let mut high = count;
        while low < high {
            let middle = low + (high - low) / 2;
            let record = self.record(first + middle)?;
            match compare_c_names(probe, record.name()) {
                Ordering::Less => high = middle,
                Ordering::Greater => low = middle + 1,
                Ordering::Equal => return Ok(Some(record)),
            }
        }
        Ok(None)
    }

    fn span(self, offset: u32, size: u32, flags: u32) -> Result<Lookup<'a>, ResourceArchiveError> {
        if flags & LOOKUP_REJECT_MASK != 0 {
            return Ok(Lookup::Missing);
        }
        if flags & RECORD_DISABLED != 0 {
            return Ok(Lookup::Disabled);
        }
        let at = usize::try_from(offset).map_err(|_| ResourceArchiveError::SizeOverflow)?;
        let size_usize = usize::try_from(size).map_err(|_| ResourceArchiveError::SizeOverflow)?;
        let bytes = self.src.get(
            at..at
                .checked_add(size_usize)
                .ok_or(ResourceArchiveError::SizeOverflow)?,
        );
        let Some(bytes) = bytes else {
            return Err(ResourceArchiveError::PayloadOutOfBounds {
                offset,
                size,
                archive_size: self.src.len(),
            });
        };
        Ok(Lookup::Found(Resource {
            offset,
            flags,
            bytes,
        }))
    }

    /// Resolve the exact archive-root-prefixed grammar used by retail.
    ///
    /// The resource manager normalizes case before this method in the game;
    /// this layer intentionally performs only the comparisons in the archive
    /// lookup itself.
    pub fn lookup(
        self,
        archive_root_name: &[u8],
        path: &[u8],
    ) -> Result<Lookup<'a>, ResourceArchiveError> {
        let (root_component, mut rest) = split_component(path);
        if root_component != archive_root_name {
            return Ok(Lookup::Missing);
        }
        if rest.is_empty() {
            return self.span(self.root.value, self.root.child_count, self.root.flags);
        }

        let mut value = self.root.value;
        let mut child_count = self.root.child_count;
        let mut flags = self.root.flags;
        loop {
            if flags & TRAVERSABLE_MASK != RECORD_CONTAINER {
                return Ok(Lookup::Missing);
            }
            let (component, next) = split_component(rest);
            let Some(record) = self.find_child(value, child_count, flags, component)? else {
                return Ok(Lookup::Missing);
            };
            value = record.value;
            child_count = record.child_count_or_size;
            flags = record.flags;
            if next.is_empty() {
                return self.span(value, child_count, flags);
            }
            rest = next;
        }
    }
}

fn split_component(path: &[u8]) -> (&[u8], &[u8]) {
    let end = path
        .iter()
        .position(|&byte| byte == b'\\' || byte == b'/')
        .unwrap_or(path.len());
    if end == path.len() {
        (path, &[])
    } else {
        (&path[..end], &path[end + 1..])
    }
}

const fn ascii_lower(byte: u8) -> u8 {
    if byte >= b'A' && byte <= b'Z' {
        byte + (b'a' - b'A')
    } else {
        byte
    }
}

fn equal_name_15_case_insensitive(name: &[u8], stored: &[u8]) -> bool {
    for index in 0..RECORD_NAME_COMPARE_SIZE {
        let left = name.get(index).copied().unwrap_or(0);
        let right = stored.get(index).copied().unwrap_or(0);
        if ascii_lower(left) != ascii_lower(right) {
            return false;
        }
    }
    true
}

fn compare_c_names(left: &[u8], right: &[u8]) -> Ordering {
    let mut index = 0;
    loop {
        let lhs = left.get(index).copied().unwrap_or(0);
        let rhs = right.get(index).copied().unwrap_or(0);
        match lhs.cmp(&rhs) {
            Ordering::Equal if lhs != 0 => index += 1,
            ordering => return ordering,
        }
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    fn put_dword(bytes: &mut [u8], at: usize, value: u32) {
        bytes[at..at + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn put_record(
        bytes: &mut [u8],
        at: usize,
        tag: u32,
        value: u32,
        count_or_size: u32,
        flags: u32,
        name: &[u8],
    ) {
        put_dword(bytes, at, tag);
        put_dword(bytes, at + 4, value);
        put_dword(bytes, at + 8, count_or_size);
        put_dword(bytes, at + 12, flags);
        bytes[at + 16..at + 32].fill(0);
        let count = name.len().min(RECORD_NAME_SIZE);
        bytes[at + 16..at + 16 + count].copy_from_slice(&name[..count]);
    }

    fn archive_with_world_tree() -> std::vec::Vec<u8> {
        let payload = b"AI!!DATA!MAP";
        let index_at = HEADER_SIZE + payload.len();
        let mut bytes = vec![0; index_at + 4 * RECORD_SIZE];
        put_dword(&mut bytes, 0, MAGIC);
        put_dword(&mut bytes, 4, 0);
        put_dword(&mut bytes, 8, 1);
        put_dword(&mut bytes, 12, RECORD_CONTAINER);
        put_dword(&mut bytes, 16, index_at as u32);
        put_dword(&mut bytes, 20, 4);
        bytes[HEADER_SIZE..index_at].copy_from_slice(payload);
        put_record(&mut bytes, index_at, 0, 1, 3, RECORD_CONTAINER, b"data");
        put_record(&mut bytes, index_at + 32, 0, 24, 4, 0, b"ai.reg");
        put_record(&mut bytes, index_at + 64, 0, 28, 5, 0, b"data.bin");
        put_record(&mut bytes, index_at + 96, 0, 33, 3, 0, b"map.reg");
        bytes
    }

    #[test]
    fn patch_style_tail_index_exposes_absolute_payload_span() {
        let payload = b"hello";
        let index_at = HEADER_SIZE + payload.len();
        let mut bytes = vec![0; index_at + RECORD_SIZE];
        put_dword(&mut bytes, 0, MAGIC);
        put_dword(&mut bytes, 4, 0);
        put_dword(&mut bytes, 8, 1);
        put_dword(&mut bytes, 12, RECORD_CONTAINER);
        put_dword(&mut bytes, 16, index_at as u32);
        put_dword(&mut bytes, 20, 1);
        bytes[HEADER_SIZE..index_at].copy_from_slice(payload);
        put_record(&mut bytes, index_at, 0, 24, 5, 0, b"patch.txt");

        let archive = ResourceArchive::parse(&bytes).unwrap();
        assert_eq!(archive.recorded_index_offset(), 29);
        assert_eq!(archive.index_offset(), 29);
        assert_eq!(archive.record_count(), 1);
        assert_eq!(archive.record(0).unwrap().name(), b"patch.txt");
        let Lookup::Found(resource) = archive.lookup(b"patch", b"patch/patch.txt").unwrap() else {
            panic!("resource was not found")
        };
        assert_eq!(resource.offset(), 24);
        assert_eq!(resource.bytes(), payload);
    }

    #[test]
    fn nested_world_paths_use_directory_child_indices() {
        let bytes = archive_with_world_tree();
        let archive = ResourceArchive::parse(&bytes).unwrap();
        let Lookup::Found(ai) = archive.lookup(b"world", b"world\\data\\AI.REG").unwrap() else {
            panic!("resource was not found")
        };
        assert_eq!(ai.bytes(), b"AI!!");
        let Lookup::Found(map) = archive.lookup(b"world", b"world/data/map.reg").unwrap() else {
            panic!("resource was not found")
        };
        assert_eq!(map.bytes(), b"MAP");
        assert_eq!(
            archive.lookup(b"world", b"main/data/map.reg").unwrap(),
            Lookup::Missing
        );
    }

    #[test]
    fn disabled_record_preserves_the_update_list_sentinel() {
        let mut bytes = archive_with_world_tree();
        let archive = ResourceArchive::parse(&bytes).unwrap();
        let flags_at = archive.index_offset() + 32 + 12;
        put_dword(&mut bytes, flags_at, RECORD_DISABLED);
        let archive = ResourceArchive::parse(&bytes).unwrap();
        assert_eq!(
            archive.lookup(b"world", b"world\\data\\ai.reg").unwrap(),
            Lookup::Disabled
        );
    }

    #[test]
    fn inline_index_flag_uses_position_after_header() {
        let mut bytes = vec![0; HEADER_SIZE + RECORD_SIZE + 1];
        put_dword(&mut bytes, 0, MAGIC);
        put_dword(&mut bytes, 4, 0);
        put_dword(&mut bytes, 8, 1);
        put_dword(&mut bytes, 12, RECORD_CONTAINER | ROOT_INDEX_INLINE);
        put_dword(&mut bytes, 16, 0xffff_ffff);
        put_dword(&mut bytes, 20, 1);
        put_record(
            &mut bytes,
            HEADER_SIZE,
            0,
            (HEADER_SIZE + RECORD_SIZE) as u32,
            1,
            0,
            b"x",
        );
        bytes[HEADER_SIZE + RECORD_SIZE] = 0xa5;
        let archive = ResourceArchive::parse(&bytes).unwrap();
        assert_eq!(archive.index_offset(), HEADER_SIZE);
        let Lookup::Found(resource) = archive.lookup(b"a", b"a/x").unwrap() else {
            panic!("resource was not found")
        };
        assert_eq!(resource.bytes(), [0xa5]);
    }

    #[test]
    fn malformed_index_children_and_payload_fail_closed() {
        assert_eq!(
            ResourceArchive::parse(&[0; HEADER_SIZE]),
            Err(ResourceArchiveError::InvalidMagic { found: 0 })
        );

        let mut bytes = archive_with_world_tree();
        let archive_size = bytes.len() as u32;
        put_dword(&mut bytes, 16, archive_size);
        assert!(matches!(
            ResourceArchive::parse(&bytes),
            Err(ResourceArchiveError::Truncated { .. })
        ));

        let mut bytes = archive_with_world_tree();
        let index_offset = ResourceArchive::parse(&bytes).unwrap().index_offset();
        put_dword(&mut bytes, index_offset + 4, 4);
        assert!(matches!(
            ResourceArchive::parse(&bytes)
                .unwrap()
                .lookup(b"world", b"world/data/ai.reg"),
            Err(ResourceArchiveError::ChildRangeOutOfBounds { .. })
        ));

        let mut bytes = archive_with_world_tree();
        let index_offset = ResourceArchive::parse(&bytes).unwrap().index_offset();
        put_dword(&mut bytes, index_offset + 32 + 4, u32::MAX);
        assert!(matches!(
            ResourceArchive::parse(&bytes)
                .unwrap()
                .lookup(b"world", b"world/data/ai.reg"),
            Err(ResourceArchiveError::PayloadOutOfBounds { .. })
        ));
    }
}
