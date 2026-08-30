# `recomp/` — execute retail code as an oracle

Byte matching proves that the reconstructed instructions equal retail. These
opt-in harnesses ask the complementary question: does retail's own mapped and
executed code produce the same result on fabricated inputs?

Nothing launches the game or captures a live session. A harness maps
`ALLODS.EXE` as data/code, applies the reviewed `config/retail/relocs.tsv` when
Wine cannot reserve the preferred base, and calls a small reachable function
family directly.

Build and run the word-RLE oracle inside `nix develop`:

```sh
recomp/harness/build.sh wordrlerun wordrle wordrletokens
wine recomp/harness/wordrlerun.exe "$ROM1_EXE" config/retail/relocs.tsv
```

The linked `wordrle*.obj` files come from `build/objdiff/base/`, so “ours” is
the exact VC5 artifact scored by objdiff, not a transcription in the harness.
The retail encoder/decoder allocation calls and the token helpers' two CRT
`memcpy` calls are redirected to the harness CRT. The six codec bodies and all
token-selection/cursor logic remain retail code; this avoids depending on the
mapped executable's uninitialized CRT jump-table state.

Build and run the network byte-Huffman oracle the same way:

```sh
recomp/harness/build.sh bytehuffmanrun bytehuffman bytehuffmannode
wine recomp/harness/bytehuffmanrun.exe "$ROM1_EXE" config/retail/relocs.tsv
```

This sweep rebuilds 1,024 code trees (including all-equal and heavily tied
frequency tables), compares all 256 code values and lengths, then compares
packed bit counts, packed bytes, decoded bytes, and 4,096 incremental
frequency-table updates. Only the retail tree allocator/free callsites are
redirected; sorting, tree construction, code generation, packing, and
unpacking all execute from the mapped retail image.

Build and run the pure BMP/DIB layout oracle the same way:

```sh
recomp/harness/build.sh dibmetricsrun dib
wine recomp/harness/dibmetricsrun.exe "$ROM1_EXE" config/retail/relocs.tsv
```

It compares null and randomized dimensions, all supported palette bit depths
plus invalid defaults, explicit `biClrUsed` overrides, DWORD-aligned scanline
sizes, explicit `biSizeImage` overrides, and the derived palette offset. The
retail methods need no import or allocator patches.

The PPM harness performs both ASCII P3 and binary P6 loads through retail and
the reconstruction, then compares parser state and every decoded byte:

```sh
rom1 build
recomp/harness/build.sh pixmaprun pixmap directxexception
wine recomp/harness/pixmaprun.exe "$ROM1_EXE" config/retail/relocs.tsv
```

The item-name harness executes retail's complete `LoadItemNames` loop on 2,050
fabricated raw files. It replaces only resource I/O, allocation, text lookup,
and map insertion edges, then checks every requested byte count and assignment:

```sh
recomp/harness/build.sh itemnamesrun
wine recomp/harness/itemnamesrun.exe "$ROM1_EXE" config/retail/relocs.tsv
```

The adjacent archive-pointer harness executes the game-owned vector serializer
in both `CArchive` modes across empty, retained-capacity, heuristic-growth,
explicit-growth, and shrink-to-zero states:

```sh
recomp/harness/build.sh archiveptrrun
wine recomp/harness/archiveptrrun.exe "$ROM1_EXE" config/retail/relocs.tsv
```
