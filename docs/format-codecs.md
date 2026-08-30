# Recovered retail format codecs

This record describes executable facts, not a guessed modernized format. The
C++ under `src/Codec/` and `src/Graphics/` is compiled with the selected VC5
SP2 profiles and compared against the listed retail RVAs. The independent
allocator-free Rust implementations live in `tools/rom1-codec/`. The harnesses
under `recomp/` map and execute the retail bodies on fabricated inputs.

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

## Windows BMP / contiguous DIB

Retail's `CDib` is the 56-byte MFC class from the
[contemporary Visual C++ DIB sample family](https://techshelps.github.io/VC%2B%2B/ch11e.htm),
with executable-confirmed field offsets and ROM-specific edits. That source
family provides the original method vocabulary; only retail bytes decide which
behavior is admitted here. The on-disk wrapper is:

```text
BITMAPFILEHEADER  14 bytes, packed to 2-byte alignment
BITMAPINFOHEADER  40 bytes
RGBQUAD palette    4 * derived_color_count bytes
pixel image        biSizeImage, or a computed DWORD-aligned image size
```

When `biClrUsed` is nonzero it is the palette count. Otherwise 1-, 4-, and
8-bpp images derive 2, 16, and 256 entries; 16-, 24-, and 32-bpp images derive
none. A zero `biSizeImage` becomes
`ceil(width * bit_count / 32) * 4 * height`.

The two retail readers are deliberately separate in the Rust API. `parse_bmp`
models `CFile::Read` and honors `bfOffBits`, retaining any safe pre-pixel gap.
`parse_bmp_contiguous` models mapped `AttachMemory`: it begins the DIB at byte
14 and derives the pixel pointer immediately after the 40-byte header and
palette, ignoring `bfOffBits`. Both preserve the recorded `biSize` without
using it as a layout offset, matching retail.

Six of eight admitted `CDib` bodies are byte-exact: dimensions, logical
palette construction, the `CFile` reader, metrics, ownership cleanup, and map
detachment. The writer at `0x04b860` is 95.85% with identical referents and
serialized field values. `ComputePaletteSize` at `0x04b990` is
instruction-for-instruction identical; its 93.85% score is the comparison
artifact from eight candidate COMDAT tail-padding bytes outside the exact FPO
extent.

The mapped-retail oracle runs 98,306 comparisons over null/random dimensions,
palette depth and `biClrUsed` combinations, explicit/computed image sizes, and
palette offsets, with zero disagreements. The allocator-free Rust codec parses
both reader modes and writes the retail packed wrapper; its tests cover offset
gaps, the mapped-reader quirk, palette rules, DWORD row alignment, exact DIB
byte preservation, and malformed bounds.

## Located next families

The campaign roster in `config/retail/serde.tsv` records high-confidence
callers without promoting guesses into source claims. The next large serde
body is the bidirectional `CArchive` scenario/save serializer at `0x0d0c97`.
The remaining DIB/BMP paths are the mapped-file wrapper at `0x04afd0` and VFW
compression at `0x04b4e0`.
