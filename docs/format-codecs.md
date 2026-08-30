# Recovered retail format codecs

This record describes executable facts, not a guessed modernized format. The
C++ under `src/Codec/` is compiled with the selected VC5 SP2 profiles and
compared against the listed retail RVAs. The independent allocator-free Rust
implementations live in `tools/rom1-codec/`. The harnesses under `recomp/` map
and execute the retail bodies on fabricated inputs.

## Word RLE

Save games and `.chr` files place a little-endian decoded-word count before a
token stream:

```text
u32 decoded_word_count

token & 0x80 != 0: (token & 0x7f) repetitions, followed by one u16 value
token & 0x80 == 0: token literal u16 values
```

Runs are capped at 127 words. The retail encoder performs one padded lookahead
read at `words[word_count]`; equality with the final word selects a repeat-one
token, while inequality selects a literal-one token. It also requests only
`2 * word_count` allocation bytes despite writing a four-byte header and token
overhead. The oracle supplies deterministic heap slack without altering codec
logic.

All six bodies are exact: top-level encode/decode at `0x11f130` and `0x11f1e0`,
and token helpers at `0x127040`, `0x127110`, `0x127210`, and `0x127290`.

## Network byte Huffman

The network buffer manager owns two packers. Their adaptive statistics are
persisted verbatim as `Packer1.dat` and `Packer2.dat`:

```text
i32 frequency[256]  // 1,024 bytes, little endian; no header
```

Loading requires one complete 1,024-byte read. The packer sorts symbol/count
pairs in descending signed-count order using the pre-2000 VC CRT `qsort`.
Equal keys retain the CRT's observable pivot/short-sort swaps; they are not
made stable. Each sorted count is incremented by one, so every byte receives a
code even with an all-zero table.

Tree insertion descends into the lighter branch (`one` wins ties), splitting a
leaf into its old symbol on the `one` branch and the new symbol on `zero`.
Generated codes use `one = 1`, `zero = 0`. Packing writes those codes
least-significant bit first and returns an exact bit count; the bit count is
carried by the surrounding network packet rather than stored in the packed
bytes.

Sixteen of 17 admitted packer functions are byte-exact, including statistics
clear/count/read/write, deterministic sort/tree reconstruction, recursive
insertion/destruction, code generation, decode, and lifecycle bodies. `Pack`
at `0x0ef939` is 99.54%: every instruction and branch is semantically aligned,
with only local stack-slot displacement bytes differing.

The mapped-retail oracle rebuilds 1,024 codebooks, explicitly including equal
frequency tables, and compares all code values, code lengths, encoded bit
counts, bytes, decoded bytes, and round trips. It also checks 4,096 incremental
frequency updates. Retail-derived FNV fixtures for zero, uniform, ascending,
and descending tables are pinned in the Rust tests, which prevents a
self-consistent but non-retail tie-order implementation from passing.

## Located next families

The campaign roster in `config/retail/serde.tsv` records high-confidence
callers without promoting guesses into source claims. The next large serde
body is the bidirectional `CArchive` scenario/save serializer at `0x0d0c97`.
The DIB/BMP family starts with file readers at `0x04afd0` and `0x04b710`, the
compression path at `0x04b4e0`, and the writer at `0x04b860`.
