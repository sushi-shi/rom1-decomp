//! The adaptive byte-Huffman stream used by the network buffer manager.
//!
//! Retail keeps two independent packers and persists each packer's 256-entry
//! little-endian frequency table as `Packer1.dat` or `Packer2.dat`. A table is
//! sorted with the VC5 CRT `qsort`, including its observable equal-key swaps,
//! then converted into a deterministic weighted binary tree. Packed bits are
//! emitted least-significant bit first and the caller carries their exact bit
//! count separately; there is no byte-stream header.

use core::fmt;

pub const SYMBOL_COUNT: usize = 256;
pub const STATISTICS_SIZE: usize = SYMBOL_COUNT * 4;
const NODE_COUNT: usize = SYMBOL_COUNT * 2 - 1;
const NO_NODE: u16 = u16::MAX;
const QSORT_CUTOFF: usize = 8;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ByteHuffmanError {
    WrongStatisticsSize { have: usize },
    OutputTooSmall { need: usize, have: usize },
    InputTooShort { need: usize, have: usize },
    SizeOverflow,
    TruncatedCodeword { at_bit: usize },
}

impl fmt::Display for ByteHuffmanError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            ByteHuffmanError::WrongStatisticsSize { have } => {
                write!(f, "statistics file is {have} bytes; retail requires 1024")
            }
            ByteHuffmanError::OutputTooSmall { need, have } => {
                write!(f, "output is {have} bytes; need {need}")
            }
            ByteHuffmanError::InputTooShort { need, have } => {
                write!(f, "input is {have} bytes; bit count requires {need}")
            }
            ByteHuffmanError::SizeOverflow => write!(f, "codec size does not fit usize"),
            ByteHuffmanError::TruncatedCodeword { at_bit } => {
                write!(f, "bitstream ends inside a codeword at bit {at_bit}")
            }
        }
    }
}

impl core::error::Error for ByteHuffmanError {}

#[derive(Clone, Copy)]
struct SymbolStats {
    symbol: u8,
    frequency: i32,
}

const EMPTY_STATS: SymbolStats = SymbolStats {
    symbol: 0,
    frequency: 0,
};

fn compare(left: SymbolStats, right: SymbolStats) -> i32 {
    if left.frequency < right.frequency {
        1
    } else if left.frequency > right.frequency {
        -1
    } else {
        0
    }
}

fn short_sort(data: &mut [SymbolStats], lo: usize, mut hi: usize) {
    while hi > lo {
        let mut max = lo;
        for at in lo + 1..=hi {
            if compare(data[at], data[max]) > 0 {
                max = at;
            }
        }
        data.swap(max, hi);
        hi -= 1;
    }
}

// VC5's pre-2000 CRT qsort. Equal elements are intentionally not stabilized:
// the middle pivot is swapped to the front, and short_sort swaps its first
// equal maximum to the end. Those permutations affect the retail codebook.
fn retail_qsort(data: &mut [SymbolStats; SYMBOL_COUNT]) {
    let mut low_stack = [0usize; 30];
    let mut high_stack = [0usize; 30];
    let mut stack_len = 0usize;
    let mut lo = 0usize;
    let mut hi = data.len() - 1;

    loop {
        let size = hi - lo + 1;
        if size <= QSORT_CUTOFF {
            short_sort(data, lo, hi);
        } else {
            let middle = lo + size / 2;
            data.swap(middle, lo);

            let mut low = lo;
            let mut high = hi + 1;
            loop {
                loop {
                    low += 1;
                    if low > hi || compare(data[low], data[lo]) > 0 {
                        break;
                    }
                }
                loop {
                    high -= 1;
                    if high <= lo || compare(data[high], data[lo]) < 0 {
                        break;
                    }
                }
                if high < low {
                    break;
                }
                data.swap(low, high);
            }
            data.swap(lo, high);

            let left_span = high as isize - 1 - lo as isize;
            let right_span = hi as isize - low as isize;
            if left_span >= right_span {
                if lo + 1 < high {
                    low_stack[stack_len] = lo;
                    high_stack[stack_len] = high - 1;
                    stack_len += 1;
                }
                if low < hi {
                    lo = low;
                    continue;
                }
            } else {
                if low < hi {
                    low_stack[stack_len] = low;
                    high_stack[stack_len] = hi;
                    stack_len += 1;
                }
                if lo + 1 < high {
                    hi = high - 1;
                    continue;
                }
            }
        }

        if stack_len == 0 {
            break;
        }
        stack_len -= 1;
        lo = low_stack[stack_len];
        hi = high_stack[stack_len];
    }
}

#[derive(Clone, Copy)]
struct Node {
    one: u16,
    zero: u16,
    one_weight: i32,
    zero_weight: i32,
    symbol: u8,
    weight: i32,
}

const EMPTY_NODE: Node = Node {
    one: NO_NODE,
    zero: NO_NODE,
    one_weight: 0,
    zero_weight: 0,
    symbol: 0,
    weight: 0,
};

fn leaf(symbol: u8, weight: i32) -> Node {
    Node {
        symbol,
        weight,
        ..EMPTY_NODE
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Statistics {
    frequencies: [i32; SYMBOL_COUNT],
}

impl Default for Statistics {
    fn default() -> Self {
        Self::new()
    }
}

impl Statistics {
    pub const fn new() -> Self {
        Self {
            frequencies: [0; SYMBOL_COUNT],
        }
    }

    pub const fn frequencies(&self) -> &[i32; SYMBOL_COUNT] {
        &self.frequencies
    }

    pub fn from_bytes(bytes: &[u8]) -> Result<Self, ByteHuffmanError> {
        if bytes.len() != STATISTICS_SIZE {
            return Err(ByteHuffmanError::WrongStatisticsSize { have: bytes.len() });
        }
        let mut result = Self::new();
        for (index, chunk) in bytes.chunks_exact(4).enumerate() {
            result.frequencies[index] =
                i32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]);
        }
        Ok(result)
    }

    pub fn write_bytes(&self, output: &mut [u8]) -> Result<(), ByteHuffmanError> {
        if output.len() < STATISTICS_SIZE {
            return Err(ByteHuffmanError::OutputTooSmall {
                need: STATISTICS_SIZE,
                have: output.len(),
            });
        }
        for (chunk, frequency) in output[..STATISTICS_SIZE]
            .chunks_exact_mut(4)
            .zip(self.frequencies)
        {
            chunk.copy_from_slice(&frequency.to_le_bytes());
        }
        Ok(())
    }

    pub fn count(&mut self, input: &[u8]) {
        for &symbol in input {
            let slot = &mut self.frequencies[usize::from(symbol)];
            *slot = slot.wrapping_add(1);
        }
    }

    pub fn codebook(&self) -> Codebook {
        Codebook::from_statistics(self)
    }
}

#[derive(Clone)]
pub struct Codebook {
    codes: [u32; SYMBOL_COUNT],
    code_bits: [u8; SYMBOL_COUNT],
    nodes: [Node; NODE_COUNT],
}

impl Codebook {
    fn from_statistics(statistics: &Statistics) -> Self {
        let mut entries = [EMPTY_STATS; SYMBOL_COUNT];
        for (index, entry) in entries.iter_mut().enumerate() {
            entry.symbol = index as u8;
            entry.frequency = statistics.frequencies[index];
        }
        retail_qsort(&mut entries);

        let mut nodes = [EMPTY_NODE; NODE_COUNT];
        nodes[0] = leaf(entries[0].symbol, entries[0].frequency.wrapping_add(1));
        let mut used = 1usize;
        for entry in &entries[1..] {
            let weight = entry.frequency.wrapping_add(1);
            let mut at = 0usize;
            loop {
                if nodes[at].one == NO_NODE {
                    let one = used;
                    let zero = used + 1;
                    used += 2;
                    nodes[one] = leaf(nodes[at].symbol, nodes[at].weight);
                    nodes[zero] = leaf(entry.symbol, weight);
                    nodes[at].one = one as u16;
                    nodes[at].zero = zero as u16;
                    nodes[at].one_weight = nodes[at].weight;
                    nodes[at].zero_weight = weight;
                    break;
                }
                if nodes[at].one_weight <= nodes[at].zero_weight {
                    nodes[at].one_weight = nodes[at].one_weight.wrapping_add(weight);
                    at = usize::from(nodes[at].one);
                } else {
                    nodes[at].zero_weight = nodes[at].zero_weight.wrapping_add(weight);
                    at = usize::from(nodes[at].zero);
                }
            }
        }
        debug_assert_eq!(used, NODE_COUNT);

        let mut result = Self {
            codes: [0; SYMBOL_COUNT],
            code_bits: [0; SYMBOL_COUNT],
            nodes,
        };
        result.build_codes();
        result
    }

    fn build_codes(&mut self) {
        let mut node_stack = [0u16; NODE_COUNT];
        let mut code_stack = [0u32; NODE_COUNT];
        let mut depth_stack = [0u8; NODE_COUNT];
        let mut stack_len = 1usize;

        while stack_len != 0 {
            stack_len -= 1;
            let at = usize::from(node_stack[stack_len]);
            let code = code_stack[stack_len];
            let depth = depth_stack[stack_len];
            let node = self.nodes[at];
            if node.one == NO_NODE {
                self.codes[usize::from(node.symbol)] =
                    code.wrapping_shr(32u32.wrapping_sub(u32::from(depth)));
                self.code_bits[usize::from(node.symbol)] = depth;
            } else {
                node_stack[stack_len] = node.zero;
                code_stack[stack_len] = code >> 1;
                depth_stack[stack_len] = depth.wrapping_add(1);
                stack_len += 1;
                node_stack[stack_len] = node.one;
                code_stack[stack_len] = (code >> 1) | 0x8000_0000;
                depth_stack[stack_len] = depth.wrapping_add(1);
                stack_len += 1;
            }
        }
    }

    pub const fn code(&self, symbol: u8) -> (u32, u8) {
        (self.codes[symbol as usize], self.code_bits[symbol as usize])
    }

    pub fn encoded_bits(&self, input: &[u8]) -> Result<usize, ByteHuffmanError> {
        let mut bits = 0usize;
        for &symbol in input {
            bits = bits
                .checked_add(usize::from(self.code_bits[usize::from(symbol)]))
                .ok_or(ByteHuffmanError::SizeOverflow)?;
        }
        Ok(bits)
    }

    pub fn encode_into(&self, input: &[u8], output: &mut [u8]) -> Result<usize, ByteHuffmanError> {
        let bit_count = self.encoded_bits(input)?;
        let byte_count = bit_count
            .checked_add(7)
            .ok_or(ByteHuffmanError::SizeOverflow)?
            / 8;
        if output.len() < byte_count {
            return Err(ByteHuffmanError::OutputTooSmall {
                need: byte_count,
                have: output.len(),
            });
        }
        output[..byte_count].fill(0);
        let mut output_bit = 0usize;
        for &symbol in input {
            let code = self.codes[usize::from(symbol)];
            let code_bits = usize::from(self.code_bits[usize::from(symbol)]);
            for code_bit in 0..code_bits {
                if code & (1u32 << code_bit) != 0 {
                    output[output_bit / 8] |= 1u8 << (output_bit & 7);
                }
                output_bit += 1;
            }
        }
        Ok(bit_count)
    }

    fn walk(
        &self,
        input: &[u8],
        bit_count: usize,
        mut emit: impl FnMut(u8),
    ) -> Result<usize, ByteHuffmanError> {
        let byte_count = bit_count
            .checked_add(7)
            .ok_or(ByteHuffmanError::SizeOverflow)?
            / 8;
        if input.len() < byte_count {
            return Err(ByteHuffmanError::InputTooShort {
                need: byte_count,
                have: input.len(),
            });
        }

        let mut consumed = 0usize;
        let mut decoded = 0usize;
        while consumed < bit_count {
            let mut at = 0usize;
            while self.nodes[at].one != NO_NODE {
                if consumed == bit_count {
                    return Err(ByteHuffmanError::TruncatedCodeword { at_bit: consumed });
                }
                let one = input[consumed / 8] & (1u8 << (consumed & 7)) != 0;
                at = usize::from(if one {
                    self.nodes[at].one
                } else {
                    self.nodes[at].zero
                });
                consumed += 1;
            }
            emit(self.nodes[at].symbol);
            decoded = decoded
                .checked_add(1)
                .ok_or(ByteHuffmanError::SizeOverflow)?;
        }
        Ok(decoded)
    }

    pub fn decoded_len(&self, input: &[u8], bit_count: usize) -> Result<usize, ByteHuffmanError> {
        self.walk(input, bit_count, |_| {})
    }

    pub fn decode_into(
        &self,
        input: &[u8],
        bit_count: usize,
        output: &mut [u8],
    ) -> Result<usize, ByteHuffmanError> {
        let need = self.decoded_len(input, bit_count)?;
        if output.len() < need {
            return Err(ByteHuffmanError::OutputTooSmall {
                need,
                have: output.len(),
            });
        }
        let mut at = 0usize;
        self.walk(input, bit_count, |symbol| {
            output[at] = symbol;
            at += 1;
        })?;
        Ok(at)
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::vec;

    use super::*;

    fn fnv1a32(mut hash: u32, bytes: &[u8]) -> u32 {
        for &byte in bytes {
            hash ^= u32::from(byte);
            hash = hash.wrapping_mul(0x0100_0193);
        }
        hash
    }

    fn codebook_hash(codebook: &Codebook) -> u32 {
        let mut hash = 0x811c_9dc5;
        for code in codebook.codes {
            hash = fnv1a32(hash, &code.to_le_bytes());
        }
        for bits in codebook.code_bits {
            hash = fnv1a32(hash, &i32::from(bits).to_le_bytes());
        }
        hash
    }

    #[test]
    fn statistics_file_is_exactly_256_little_endian_dwords() {
        let mut stats = Statistics::new();
        stats.count(&[0, 0, 1, 255]);
        let mut bytes = [0u8; STATISTICS_SIZE];
        stats.write_bytes(&mut bytes).unwrap();
        assert_eq!(&bytes[0..8], &[2, 0, 0, 0, 1, 0, 0, 0]);
        assert_eq!(&bytes[1020..1024], &[1, 0, 0, 0]);
        assert!(matches!(
            Statistics::from_bytes(&bytes[..1023]),
            Err(ByteHuffmanError::WrongStatisticsSize { have: 1023 })
        ));
        assert_eq!(Statistics::from_bytes(&bytes).unwrap(), stats);
    }

    #[test]
    fn every_symbol_round_trips_with_the_zero_statistics_table() {
        let stats = Statistics::new();
        let codebook = stats.codebook();
        let mut input = [0u8; SYMBOL_COUNT];
        for (index, value) in input.iter_mut().enumerate() {
            *value = index as u8;
        }
        let bits = codebook.encoded_bits(&input).unwrap();
        let mut encoded = vec![0u8; (bits + 7) / 8];
        assert_eq!(codebook.encode_into(&input, &mut encoded).unwrap(), bits);
        let mut decoded = [0u8; SYMBOL_COUNT];
        assert_eq!(
            codebook.decode_into(&encoded, bits, &mut decoded).unwrap(),
            input.len()
        );
        assert_eq!(decoded, input);
    }

    #[test]
    fn codebooks_and_zero_table_stream_match_mapped_retail_fixtures() {
        let zero = Statistics::new().codebook();
        assert_eq!(codebook_hash(&zero), 0x4325_a1c5);

        let mut one_stats = Statistics::new();
        one_stats.frequencies.fill(1);
        assert_eq!(codebook_hash(&one_stats.codebook()), 0x4325_a1c5);

        let mut ascending = Statistics::new();
        let mut descending = Statistics::new();
        for index in 0..SYMBOL_COUNT {
            ascending.frequencies[index] = index as i32;
            descending.frequencies[index] = (SYMBOL_COUNT - 1 - index) as i32;
        }
        assert_eq!(codebook_hash(&ascending.codebook()), 0x647c_0dc5);
        assert_eq!(codebook_hash(&descending.codebook()), 0x454f_85c5);

        let mut all_symbols = [0u8; SYMBOL_COUNT];
        for (index, symbol) in all_symbols.iter_mut().enumerate() {
            *symbol = index as u8;
        }
        let mut packed = [0u8; SYMBOL_COUNT];
        let bits = zero.encode_into(&all_symbols, &mut packed).unwrap();
        assert_eq!(bits, 2048);
        assert_eq!(fnv1a32(0x811c_9dc5, &packed), 0x0f06_ffc5);
    }

    #[test]
    fn trained_binary_distribution_round_trips_across_word_boundaries() {
        let mut stats = Statistics::new();
        stats.count(b"aaaaaaaaaaaaabbbbccdefghijklmnopqrstuvwxyz");
        let codebook = stats.codebook();
        let input = b"allods network packer: least-significant-bit first";
        let bits = codebook.encoded_bits(input).unwrap();
        let mut encoded = vec![0u8; (bits + 7) / 8];
        codebook.encode_into(input, &mut encoded).unwrap();
        let mut decoded = [0u8; 52];
        assert_eq!(
            codebook.decode_into(&encoded, bits, &mut decoded).unwrap(),
            input.len()
        );
        assert_eq!(&decoded[..input.len()], input);
    }

    #[test]
    fn malformed_inputs_fail_closed() {
        let codebook = Statistics::new().codebook();
        assert!(matches!(
            codebook.decoded_len(&[], 1),
            Err(ByteHuffmanError::InputTooShort { .. })
        ));

        let (code, bits) = codebook.code(0);
        assert!(bits > 1);
        let partial = [code as u8];
        assert!(matches!(
            codebook.decoded_len(&partial, usize::from(bits - 1)),
            Err(ByteHuffmanError::TruncatedCodeword { .. })
        ));
    }
}
