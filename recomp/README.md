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
