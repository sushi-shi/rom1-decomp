# Setup status

The RoM1 decompilation environment was bootstrapped on 2026-08-29 from Gruntz
commit `00960e4a9beb6dfbf3f7e604bd5050ef8bf5e078`.

The retail foundation is reproducible from the pinned executable:

| Channel | Exact rows | Tracked file |
| --- | ---: | --- |
| FPO function extents/frame metadata | 4,384 | `config/retail/functions_fpo.tsv` |
| Recovered DIR32 sites | 32,454 | `config/retail/relocs.tsv` |
| Strings | 10,296 | `config/retail/strings.tsv` |
| Imports | 472 across 14 DLLs | `config/retail/imports.tsv` |
| PE sections | 5 | `config/retail/sections.tsv` |
| Debug directory records | 3 | `config/retail/debug.tsv` |

The complete FPO partition, not a disassembler guess, seeds `functions.tsv`.
The recovered relocation list is consumed both by the Python delink model and
Vostok's `--reloc-manifest`; the empty PE relocation directory is never used as
a fallback.

The first static-library pass is ready and recorded under `config/evidence/`.
Against the rejected VC5 SP3 bootstrap it finds 1,021 unique exact and 1,150
colliding FPO extents (2,171 total), primarily from `LIBCMT`, `LIBCIMT`, and
`NAFXCW`. Those rows are ancestry evidence only and cannot be promoted. The
same scan over both surviving SP1/SP2 payloads is the compiler decision panel.

DirectX 5 is fetched by exact SHA-256 and overlays the Gruntz bootstrap's DX6
directory. RoM1 does not import DInput or DPlay. Smacker is prepared under
`vendor/smacker-3.1l/` with byte-exact upstream originals, one admitted patch,
and executable/runtime ABI checks.

The only hard setup gap is acquisition of complete VC5 SP1 and SP2 payloads.
The PE linker stamp rejects RTM and SP3, but SP1 and SP2 share linker version
5.02.7132. The build intentionally refuses to compile until the complete
archive census selects one and records exact hashes in `compiler.toml`.
