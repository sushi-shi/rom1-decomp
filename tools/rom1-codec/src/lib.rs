//! Clean-room codecs for Rage of Mages 1 data formats.
//!
//! This crate is independent of the reconstructed C++ under `src/`. Its
//! grammars come from retail `ALLODS.EXE` disassembly and shipped data only.
//! APIs borrow their input and write into caller-owned buffers, so the crate
//! needs neither `std`, an allocator, nor third-party dependencies.

#![no_std]

pub mod word_rle;

pub(crate) enum Sink<'a> {
    Count(usize),
    Write { bytes: &'a mut [u8], at: usize },
}

impl Sink<'_> {
    pub(crate) fn push(&mut self, byte: u8) -> bool {
        match self {
            Sink::Count(count) => {
                *count += 1;
                true
            }
            Sink::Write { bytes, at } => match bytes.get_mut(*at) {
                Some(slot) => {
                    *slot = byte;
                    *at += 1;
                    true
                }
                None => false,
            },
        }
    }

    pub(crate) fn extend(&mut self, data: &[u8]) -> bool {
        match self {
            Sink::Count(count) => {
                *count += data.len();
                true
            }
            Sink::Write { bytes, at } => match bytes.get_mut(*at..*at + data.len()) {
                Some(slot) => {
                    slot.copy_from_slice(data);
                    *at += data.len();
                    true
                }
                None => false,
            },
        }
    }

    pub(crate) fn len(&self) -> usize {
        match self {
            Sink::Count(count) => *count,
            Sink::Write { at, .. } => *at,
        }
    }
}
