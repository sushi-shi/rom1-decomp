# Rage of Mages 1 / Allods decompilation

Binary-matching reconstruction of the original Windows release of **Rage of
Mages / Allods** (Monolith Productions, 1998). The target is the Russian Buka
`Hello__0` engine:

```text
ALLODS.EXE  1,979,392 bytes
SHA-256     5ba821f37356d2da0e1eb907de28b2708714d6e2604b5caef3daf4284b9af7d3
```

The repository deliberately mirrors the Gruntz decompilation workflow and
command surface. RoM1-specific facts are generated from the executable and
kept in `config/retail/`; Gruntz facts are never carried over as game evidence.

## Current foundation

- 4,384 exact FPO records with function extents and full frame metadata;
- 32,454 recovered absolute-relocation sites in `config/retail/relocs.tsv`;
- 10,296 addressable ASCII/UTF-16 strings;
- exact PE, section, debug, and 472-import inventories;
- pinned Vostok plus the local relocation-manifest recovery path;
- a complete relocation-masked static-library census over every FPO extent;
- exact DirectX 5 headers/import libraries;
- the complete 16-function Smacker 3.1L ABI used by retail, checked against the
  exact runtime DLL and a patched, provenance-preserving closest header;
- the Gruntz-shaped CLI, Ninja graph, delinker, objdiff, verification, Ghidra,
  semantic-navigation, wall, and permutation infrastructure.

The executable linker stamp is `5.02`. Microsoft's VC5 servicing table leaves
SP1 and SP2 as the two candidates; both payloads are still required for the
deciding archive census. The available Gruntz SP3 payload is therefore an
**analysis bootstrap only**. Compile and link commands fail closed until
`config/compiler.toml` records an executable-proven selection.

## Start here

```sh
nix develop .#inventory              # broad archive/media/RE toolbox
nix develop                          # matching environment and bootstrap tools

rom1 tool retail-census              # verify PE/FPO/import/string evidence
rom1 tool relocs                      # verify/regenerate recovered relocations
rom1 tool vendor                      # verify Smacker header ABI + runtime
rom1 tool compiler-census             # show the finite VC5 servicing matrix
```

Once both SP1/SP2 payloads are available:

```sh
rom1 tool compiler-census \
  --candidate vc5-sp1=/path/to/sp1 --candidate vc5-sp2=/path/to/sp2 --write
```

Only then can a real source campaign begin with `rom1 build` / `rom1 match`.
See [the setup record](docs/setup-status.md), [compiler evidence](docs/compiler-detection.md),
and [the Gruntz parity contract](docs/gruntz-parity-contract.md).

## Licensing

Repository-owned work is dedicated under CC0 1.0 using the exact license text
from the HoMM2 project. Third-party material retains its own notices and terms;
see [THIRD_PARTY.md](THIRD_PARTY.md).
