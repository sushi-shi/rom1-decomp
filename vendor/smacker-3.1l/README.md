# Smacker 3.1L imported ABI

RoM1 ships `SMACKW32.DLL` 3.1L and imports 16 decorated Win32 functions from
it. The redistributable runtime is fetched by `flake.nix`; it is not committed.

The closest public SDK source found is
[`edgeforce/radtools`](https://github.com/edgeforce/radtools), pinned here at
commit `f42d146c164f264d22e593827a2a028e45fd83d6`. Its `smack.h` identifies as
3.2f and is byte-identical to the recovered 3.2f header used by the Gruntz
project. The official RAD history says the SmackBlit API arrived in 3.1a; the
later 3.1L and 3.2f notes do not describe an imported-API signature change.

Layout:

- `orig/` is the byte-exact pinned GitHub input;
- `patches/0001-retail-version.patch` is the admitted version adjustment;
- `rad.h` and `smack.h` are the materialized include tree used by RoM1, at the
  same one-directory-deep location as Gruntz's vendor headers;
- `retail_imports.tsv` is generated directly from ALLODS.EXE.

Run `rom1 tool vendor`. It verifies original hashes, reconstructs the patched
header, checks every prototype's x86 stdcall byte count against the executable's
decorated imports, checks that all imports are exported by the pinned retail
DLL, and requires both the DLL SHA-256 and its embedded 3.1L identity.

This makes the complete RoM1-used ABI exact. It does **not** assert that
unimported declarations or header comments are a byte-for-byte recovered 3.1L
SDK. Those remain closest-source evidence until a genuine 3.1L SDK is found.
