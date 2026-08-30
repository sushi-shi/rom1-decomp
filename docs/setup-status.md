# Setup status

The RoM1 decompilation environment was bootstrapped on 2026-08-29 from Gruntz
commit `00960e4a9beb6dfbf3f7e604bd5050ef8bf5e078`.

The retail foundation is reproducible from the pinned executable:

| Channel | Exact rows | Tracked file |
| --- | ---: | --- |
| Manual function census | 12,563 | `config/retail/functions.tsv` |
| Analyzer start evidence | 6,659 | `config/retail/functions_disasm.tsv` |
| FPO function extents/frame metadata | 4,384 | `config/retail/functions_fpo.tsv` |
| Global `/GX` EH partition | 4,134 | `config/retail/eh_actions.tsv`, `eh_groups.tsv` |
| C++ initializer helpers | 147 | `config/retail/dyninit.tsv` |
| Pure IAT jump thunks | 2 | `config/retail/thunks.tsv` |
| MFC runtime classes / vtables | 117 / 358 | `runtime_classes.tsv`, `vtables.tsv` |
| Structured data starts | 3,476 | `config/retail/data.tsv` |
| Recovered DIR32 sites | 32,454 | `config/retail/relocs.tsv` |
| Strings | 10,296 | `config/retail/strings.tsv` |
| Imports | 472 across 14 DLLs | `config/retail/imports.tsv` |
| PE sections | 5 | `config/retail/sections.tsv` |
| Debug directory records | 3 | `config/retail/debug.tsv` |

`functions.tsv` was seeded once from the analyzer/FPO/structure union and is
manually maintained thereafter, as in Gruntz. The 4,384 FPO records are the
exact-extent subset, not the whole function partition. `retail-partition`
regenerates the companion evidence and validates every required FPO, EH,
initializer, and thunk start without rewriting manual decisions. A masked FID
off-start pass added 28 reviewed starts; its next pass found zero remaining
padding-boundary candidates.

The recovered relocation list is consumed both by the Python delink model and
Vostok's `--reloc-manifest`; the empty PE relocation directory is never used as
a fallback.

The first static-library pass is ready and recorded under `config/evidence/`.
Against the rejected VC5 SP3 bootstrap, the conservative FPO panel finds 1,001
bijective exact and 1,170 ambiguous extents (2,171 total). The Gruntz-style
full manual-start FID finds 1,336 globally unique exact providers: 851
`NAFXCW`, 413 `LIBCMT`, and 72 `LIBCIMT`. Those rows are ancestry evidence only
and cannot be promoted. The same scans over complete SP1 and SP2 payloads are
the compiler decision panel.

DirectX 5 is fetched by exact SHA-256 and overlays the Gruntz bootstrap's DX6
directory. RoM1 does not import DInput or DPlay. Smacker is prepared under
`vendor/smacker-3.1l/` with byte-exact upstream originals, one admitted patch,
and executable/runtime ABI checks.

Zlib 1.0.4 was tested rather than inherited from Gruntz. The old inventory
candidate was verified through a2server, which is RoM2 lineage and is not a
RoM1 witness. A relocation-masked probe of all 4,384 FPO extents against
Gruntz's archive produced 126 forward hits, but every hit was the same generic
six-byte `_zlibVersion` body (`mov eax,<reloc>; ret`) and that candidate matched
126 different retail functions. The complete manual-census FID then tested all
66 substantive archive signatures at 12,563 starts plus strict off-start
boundaries and found zero matches. Retail also contains none of zlib 1.0.4's
identity or diagnostic strings. Both negative controls are tracked under
`config/evidence/`; no zlib source is vendored without a substantive RoM1
executable witness.

The only hard setup gap is acquisition of complete VC5 SP1 and SP2 payloads.
The PE linker stamp rejects RTM and SP3, but SP1 and SP2 share linker version
5.02.7132. The build intentionally refuses to compile until the complete
archive census selects one and records exact hashes in `compiler.toml`.

The source manifest's empty state is explicit: `[build] bootstrap=true` emits
the full zero-TU Ninja graph and its committed zero-debt gate baselines. The
first admitted `[[unit]]` must remove that marker, so an accidentally vacuous
campaign manifest still fails. The ported verification harness passes all 429
controls in the pinned shell (11 build-dependent controls skip before a TU).
