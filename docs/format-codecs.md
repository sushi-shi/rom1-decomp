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

## Save-game envelope

The save writer at `0x0cee6f` serializes the scenario into memory, rounds an
odd byte count up to a word, word-RLE encodes it, and writes this envelope:

```text
u32 magic = 0x26677341       // little-endian bytes "Asg&"
u32 declared_file_size       // backpatched after all writes
u32 version = 0x0bad0002
u32 compressed_byte_count
u8  word_rle[compressed_byte_count]
u8  server_description[256]  // optional
```

For an odd serialized scenario length, retail increments the length and writes
its new low byte as the padding byte before compression; that is not assumed
to be zero. In server-multiplayer mode the writer appends the NUL-terminated
text `Server Multiplayer save file.` and zero-fills the rest of a fixed
256-byte record. The backpatched file size includes that record.

The reader at `0x0cf1ee` validates the magic and accepts a version using the
signed comparison `version >= 0x0bad0002`. It reads but never validates the
declared file size, and it ignores everything after the declared compressed
extent. The safe Rust parser preserves those compatibility rules while
rejecting a compressed extent outside the supplied slice; its writer emits
the canonical current version and optional fixed server record.

The mapped-retail oracle runs 2,050 inputs spanning open failure, invalid
magic, old and sign-bit-set versions, current/future versions, arbitrary
declared lengths, and zero/random compressed sizes. It reports zero
disagreements over 16,180 control/extent checks and 1,330 compressed-payload
checks.

## Character `.chr` envelope

The character writer at `0x0cf4f0` serializes one character, word-RLE encodes
it, and creates a payload in a 14-byte network record. The disk file is exactly
the record payload, not its transport header:

```text
u32 metadata[4]              // four non-contiguous character fields
u8  word_rle[]
u8  zero_pad[word_rle_size & 1]
```

The original semantic names of the four metadata words are not yet proven, so
the codec preserves them without inventing field identities. The transport
header stores the complete payload length in words. Disk loading computes that
word count with `file_length >> 1`; one odd physical trailing byte is therefore
ignored. The writer itself always produces an even file and writes zero for
its possible compressed-stream pad.

The reader at `0x0cf8b8` copies exactly 16 metadata bytes, computes the
compressed extent as `payload_words * 2 - 16`, and passes that entire region,
including the possible zero pad, to word-RLE. The mapped oracle reports zero
disagreements over 14,336 extent checks and 6,144 metadata/payload checks on
2,048 randomized packets. The safe Rust parser rejects a truncated metadata
prefix and exposes the retail-ignored odd tail separately.

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

## CPixMap P3/P6 PPM

The 36-byte `CPixMap` family at `0x08d1e0`–`0x08d5e0` detects `.pcx`, `.ppm`,
`.bmp`, and `.dib` with case-sensitive `CString::Find` calls. Its dispatcher
throws a pointer to an 8-byte `CDirectXException` for an unknown type. The BMP
and PCX loader arms are deliberate `TRUE` stubs; only the PPM arm contains a
parser.

Retail accepts the ASCII P3 and binary P6 magic prefixes and always configures
24-bit pixels with three 8-bit components. Its grammar is narrower than a
general Netpbm reader:

```text
P3 or P6, inspected as the first two bytes of one 100-byte fgets buffer
zero or more lines beginning with '#' in column zero
width and height as two signed decimal ints on one line
one complete max-value line, read and discarded without parsing
width * height * 3 components
```

P6 copies the component bytes verbatim. P3 scans signed decimal `int` values
and stores each low byte, so negative and greater-than-255 components truncate
rather than scale or clamp. Comments are recognized only in the one header
position above; leading whitespace prevents comment recognition. Unknown
magic returns `TRUE` without pixels, and neither the max value nor trailing
bytes are validated.

Six of the nine ordinary `CPixMap` methods are byte-exact: both constructors,
destruction/cleanup, and the BMP/PCX success stubs. File-type detection is
99.32%, dispatch is 99.87%, and PPM loading is 99.83%; their instruction
streams align with retail, while pooled-string, throw-metadata, and generic CRT
referent identities keep the object comparison below 100%. The required
`CDirectXException` constructor is 99.77% for the same referent-only reason.

The mapped-retail oracle redirects only allocation and stdio call edges into
the harness, then executes both parser bodies on 512 P3 and 512 P6 files. It
reports zero disagreements over 9,216 result/field comparisons and 56,156
decoded-byte comparisons. The allocator-free Rust API preserves the retail
grammar and successful unknown-magic no-op while rejecting truncated input,
invalid dimensions, 32-bit allocation overflow, and undersized output that
would make the original consume or expose unsafe memory.

## Game `.res` archive namespace

The game archive reader at `0x0c9070` is reached directly from startup, not
inferred from file extensions. The game `CWinApp::InitInstance` override at
`0x070b40` mounts `graphics.res`, `main.res`, `patch.res`, `music.res`,
`video4.res`, `video8.res`, `sfx.res`, `movies.res`, `scenario.res`, and
`speech.res`, in that order, through the mount wrapper at `0x0c98e0`. It then
passes `update.lst` to the line reader at `0x0c99f0` before opening typed
resources such as `main\\text\\itemname.bin`. The line reader, disabled-record
marker, shared path walker, and final-record filter are all byte-exact.

This `.res` is the game's own tree container and is unrelated to a Win32
compiled-resource file:

```text
u32 root_tag = 0x31415926
u32 root_first_child
u32 root_child_count
u32 root_flags
u32 index_offset
u32 record_count
u8  payload[]
Record records[record_count]  // normally at index_offset

Record = {
    u32 tag
    u32 value                 // child index for a directory, file offset otherwise
    u32 child_count_or_size
    u32 flags
    u8  name[16]
}
```

The shared tree walker at `0x0ce7e0` first consumes the archive base name,
then traverses slash- or backslash-separated components. Ordinary child
lookup compares at most 15 bytes case-insensitively. The less-common sorted
directory path uses the retail case-sensitive record comparator. The final
lookup at `0x0c92f0` returns the archive's `CFile`, absolute payload offset,
and byte length. `CResourceFile::Read` at `0x0ca100` seeks that owner to
`offset + position`, clamps reads to the recorded length, and advances the
view position.

`update.lst` is one printable resource path per line. The reader strips LF
and CR and the marker at `0x0c9aa0` finds the first matching mounted record
and sets flag `0x20000000`. Later lookup returns a distinct sentinel for that
record, preventing fallback into an older archive. This is an overlay
suppression list, not another serialized object stream.

The independent `no_std` Rust parser preserves tail and inline index modes,
the directory/leaf field duality, the two name-comparison modes, and the
disabled-record result. It rejects malformed index, child, and payload
extents. The `res_inspect` example lists an archive and resolves an optional
root-prefixed path. It has been exercised against the local retail
`PATCH.RES`, `WORLD.RES`, `MAIN.RES`, and `SCENARIO.RES`; in particular,
`main\\text\\itemname.bin` resolves to offset `0x1ff7`, length `0x340` in the
examined retail `MAIN.RES`. No retail bytes are stored in the repository.

## Startup text resources

The startup xrefs continue from archive lookup into the typed reader at
`0x068660`. The `CWinApp::InitInstance` override calls it for
`main\\text\\main.txt`, `heropicture.txt`, `stats.txt`, `spells.txt`,
`spell.txt`, `dialogs.txt`, `unitname.txt`, `building.txt`, `itemname.txt`,
`sites.txt`, `npcnames.txt`, `cutscene.txt`, `cutpaths.txt`, `tunes.txt`, and
finally `patch\\patch.txt`. This is the deserializer for the shared startup
text-table format, not merely a filename or archive-extension inference.

Retail reads the complete resource into one allocation and repeatedly applies
this grammar until the cursor reaches the allocation end:

```text
record_bytes[]
u8 carriage_return = 0x0d  // overwritten with NUL in place
u8 skipped_byte            // 0x0a in shipped CRLF data; never checked
```

Each record start is appended to one global pointer vector. The 16-byte text
block descriptor keeps the allocation, record count, and its starting vector
index. The loop is a do-while and scans without a bound for the next CR, so an
empty file, a missing CR, or a final CR without its following byte reaches
unsafe memory in retail. The independent Rust parser rejects those cases,
preserves the unchecked post-CR byte, and emits canonical CRLF records.

Two neighboring startup readers establish the consumers. `0x0683e0` reads
`main\\text\\help.txt` in full, appends one NUL byte, and assigns the result
to its string owner. After `patch\\patch.txt` is loaded through the shared
table reader, `0x069220` finds `=` in every patch record and passes its
`Left` and `Mid` substrings into the patch mapping. `LoadItemNames` then joins
the already-loaded `itemname.txt` record positions to `itemname.bin` IDs.

Startup also reaches the Bute reader through `0x063760`, which opens
`Scenario\\GlobalMap.reg`, reads `General/ObjectCount`, then reads indexed
`MapObject%d` point, rectangle, and picture fields. The exact helper at
`0x0878a0` reads `MissionObjects/Mission%d`; `0x08a330` follows those indices
back to `MapObject%d` and reads `Picture` and `PictureOffset`. These are the
first typed resource-config deserializers identified from the startup chain.

## Item-name ID table

`LoadItemNames` at `0x068490` opens `main\\text\\itemname.bin`. The file is a
headerless sequence rather than a general text container:

```text
u16 item_id[]  // little endian; file position is the text-block index
```

Retail computes `item_count = file_length >> 1`, allocates and reads exactly
`item_count * 2` bytes, and ignores one odd trailing byte. For each entry it
looks up the string at the same zero-based position in the already-loaded
item-name text block and assigns that pointer to the word-keyed global map.
Duplicate IDs therefore issue duplicate map assignments in file order, with
the final pointer retained by the real map.

The loader is 98.77% and instruction-aligned. Its remaining comparison residue
is the provisional identity of the game-owned resource-file methods; the
loader's exact callees, count arithmetic, loop, globals, and map operation are
all located. The mapped-retail oracle executes 2,050 fabricated inputs and
reports zero disagreements over 18,450 file/control checks and 1,046,842
key/value assignment checks. The allocator-free Rust view exposes complete
little-endian IDs, the consumed byte count, and the ignored tail explicitly;
its canonical writer never emits an odd tail.

## CArchive raw pointer vector

The game-owned 20-byte vector at `0x5eb328` has the same data/size/max/growth
layout and resize policy as the contemporary MFC pointer array, but its
`0x599630` vtable has the game class's own runtime identity. Its serializer at
`0x069390` is bidirectional:

```text
count < 0xffff: u16 count
otherwise:      u16 0xffff, u32 count
u32 pointer_word[count]
```

The count prefix is the 32-bit MFC `CArchive::WriteCount` format. After it,
retail passes the pointer array directly to `CArchive::Write` or `Read`. These
words are process addresses, not stable string IDs; the Rust codec preserves
them as raw little-endian `u32` values and deliberately labels the format as
an address snapshot.

The reconstructed serializer has the exact `0x188` retail extent and an
81.44% fuzzy score. Its call sequence, constants, archive-mode branches, and
semantics agree; residual instructions are concentrated in VC5 register
scheduling for the inlined resize routine. The mapped-retail oracle exercises
2,048 randomized store/load pairs across every allocation state and reports
zero disagreements over 38,399 call/state checks and 4,094 raw-word checks.
The Rust parser additionally rejects truncated count prefixes, truncated word
arrays, size overflow, and undersized writer output.

## Complete first-pass candidate wall

The first-pass retail census is reproducible from two stronger signals than
names or strings. MFC's five-entry `CObject` virtual prefix fixes `Serialize`
at slot 2, so the recovered vtable catalog proves 151 non-default overrides.
The call graph then walks through incremental-link thunks to the reviewed
archive/file/stdio roots in `config/retail/serde_roots.tsv`. The union is 284
distinct exact RVAs: 223 reach archive reads, 189 archive writes, one a
container serializer, 11 binary-file reads, nine binary-file writes, and ten
stdio readers; categories overlap.

The initial result was admitted once to
`config/retail/serde_candidates.tsv`. That table is manually maintained from
this point, like `functions.tsv`. `rom1 sema serde --write-report` writes only
the derived `build/gen/serde_candidates.tsv`, while
`rom1 verify serde-coverage` compares every RVA and evidence signal against
the manual wall. New, disappearing, reclassified, and signal-changed rows all
fail until reviewed.

The first source unit selected from that wall is now exact for all 12 admitted
bodies and all 857 instruction bytes. Eight are the complete recovered
TableLine slot-2 cluster at `0x0df278`–`0x0e03d2`; one is the embedded-CObject
serializer at `0x111b15`; and three are the exact VC5 SP2 `IsStoring`,
`CStringArray::operator[]`, and `CStringArray::ElementAt` COMDATs emitted by
the source forms. The runtime class fixes TableLine's 28-byte size. Retail
constructors and serializers then independently fix a CString at `+0x04`, a
nested polymorphic object at `+0x08`, five raw WORDs, fixed two- and ten-entry
CStringArray loops, a raw 72-byte record, and CString extensions. Names that
did not survive remain evidence-neutral rather than guessed.

The four raw-record serializers at `0x13db00`, `0x13dbc0`, `0x13dc80`, and
`0x13dcc0` are also exact. The first three apply the same bidirectional
complete-object archive operation to 0x50-, 0x48-, and 0x0c-byte records. The
fourth writes or reads a 24-byte owner and then dispatches two game-owned list
serializers. Its load arm deletes the old lists, allocates two 28-byte MFC-list
layouts with block size ten, and overwrites the stale raw pointers before
virtual dispatch. The list vtables and slot-2 element widths prove the class
shapes, but no original class names survive, so the source names record only
those evidenced roles.

The ANSI CString bytes are the exact VC5 SP2 `ARCCORE.CPP` grammar that the
retail static-library operators implement:

```text
length < 0xff:   u8 length
length < 0xfffe: u8 0xff, u16 length
otherwise:       u8 0xff, u16 0xffff, u32 length
u8 bytes[length]
```

The mapped-retail harness executes the actual retail CString length
encoder/decoder and all eight slot-2 bodies in both archive modes. Over 2,048
fabricated layout cases it reports zero disagreements for 6,144 store-byte,
18,176 load/state, and 4,096 nested-dispatch checks. It deliberately redirects
only primitive archive I/O, CString output allocation, and polymorphic nested
objects. The independent `no_std` Rust module implements the same three
length prefixes and all six distinct compositional layouts; nested-object byte
slices remain caller-supplied because retail stores no artificial boundary
around a virtual serializer.

The bidirectional scenario/save serializer at `0x0d0c97` is now exact across
its complete `0x94b` retail extent and all 112 ordered relocations. Recovered
source fixes the `CReferenceWorld` layout, save/load branch structure,
iterator-current fields, signed mode guard, global scenario path referent, and
the ownership and call identities of its support objects. Its tail reaches the
separately exact `CReferenceSnapshot::Serialize` at `0x13e840`, whose store and
load branches transfer one raw `0x190`-byte snapshot.

The world-map serializer at `0x144aa0` is source-complete at 84.81%. Its store
arm scans tile indices `0x0807` through `0xeded`, packs exceptional high-byte
tiles as index/high/low DWORDs, then serializes the list, an embedded
`CMap<WORD, WORD, CWorldMapRecord, CWorldMapRecord&>`, and the raw process
pointer identity. Its load arm restores that pointer through `CReferenceWorld`
and unpacks the tile list. The emitted `CList<DWORD, DWORD>::Serialize` body at
`0x1503e0` is independently byte-exact. The parent remains on the candidate
wall because VC5 expands a different pair of archive primitives; diagnosis and
two bounded permutation campaigns identify TU inline context, rather than a
source-semantic discrepancy, as the remaining lever.

The remaining DIB/BMP paths are the mapped-file wrapper at `0x04afd0` and VFW
compression at `0x04b4e0`.
