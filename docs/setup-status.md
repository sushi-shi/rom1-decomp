# Setup status

The RoM1 decompilation environment was bootstrapped on 2026-08-29 from Gruntz
commit `00960e4a9beb6dfbf3f7e604bd5050ef8bf5e078`.

The retail foundation is reproducible from the pinned executable:

| Channel | Exact rows | Tracked file |
| --- | ---: | --- |
| Manual function census | 13,023 | `config/retail/functions.tsv` |
| Analyzer start evidence | 6,659 | `config/retail/functions_disasm.tsv` |
| FPO function extents/frame metadata | 4,384 | `config/retail/functions_fpo.tsv` |
| Global `/GX` EH partition | 4,134 | `config/retail/eh_actions.tsv`, `eh_groups.tsv` |
| C++ initializer helpers | 147 | `config/retail/dyninit.tsv` |
| Pure IAT jump thunks | 474 | `config/retail/thunks.tsv` |
| MFC runtime classes / all proven vtables | 117 / 425 | `runtime_classes.tsv`, `vtables.tsv`, `data_vtables.tsv` |
| Structured data starts | 5,772 | `config/retail/data.tsv` |
| Recovered DIR32 sites | 32,454 | `config/retail/relocs.tsv` |
| Strings | 10,296 | `config/retail/strings.tsv` |
| Imports | 472 across 14 DLLs | `config/retail/imports.tsv` |
| PE sections | 5 | `config/retail/sections.tsv` |
| Debug directory records | 3 | `config/retail/debug.tsv` |

`functions.tsv`, `data.tsv`, and `data_vtables.tsv` were seeded once and are
manually maintained thereafter, as in Gruntz. The 4,384 FPO records are the
exact-extent subset, not the whole function partition. `retail-partition`
regenerates companion evidence and validates every required FPO, EH,
initializer, thunk, data, and vtable start without rewriting manual decisions.
A masked FID off-start pass added 28 reviewed starts; its next pass found zero
remaining padding-boundary candidates.

The recovered relocation list is consumed both by the Python delink model and
Vostok's `--reloc-manifest`; the empty PE relocation directory is never used as
a fallback.

The complete official VC5 SP2 payload is selected and recorded under
`config/evidence/`. Its conservative FPO panel finds 1,010 bijective exact and
1,170 ambiguous extents (2,180 total), nine more bijective witnesses than the
rejected SP3 control. The Gruntz-style full manual-start FID promotes 1,354
globally unique exact providers: 861 `NAFXCW`, 421 `LIBCMT`, and 72 `LIBCIMT`;
one separately reviewed `operator delete` provider brings the committed table
to 1,355. Ambiguous rows remain evidence-only. SP1 is a fallback to acquire
only if a later representative SP2 compilation witness fails.

DirectX 5 is fetched by exact SHA-256 and overlays the Gruntz bootstrap's DX6
directory. RoM1 does not import DInput or DPlay. Smacker is prepared under
`vendor/smacker-3.1l/` with byte-exact upstream originals, a retail-version
patch, a metadata-only Clang compatibility patch, and executable/runtime ABI
checks. The VC5 compilation path retains the upstream inline assembly.

Zlib 1.0.4 was tested rather than inherited from Gruntz. The old inventory
candidate was verified through a2server, which is RoM2 lineage and is not a
RoM1 witness. A relocation-masked probe of all 4,384 FPO extents against
Gruntz's archive produced 126 forward hits, but every hit was the same generic
six-byte `_zlibVersion` body (`mov eax,<reloc>; ret`) and that candidate matched
126 different retail functions. The complete manual-census FID then tested all
80 substantive archive signatures and 7,143 controls at 13,023 starts plus
strict off-start boundaries and found zero matches. Retail also contains none
of zlib 1.0.4's
identity or diagnostic strings. Both negative controls are tracked under
`config/evidence/`; no zlib source is vendored without a substantive RoM1
executable witness.

The compiler setup gate is closed: SP2 `LINK.EXE` 5.2.0.7132 agrees with the PE
stamp, all seven compiler/linker roles are present, and the complete tool and
archive aggregates are pinned in `compiler.toml`. Compile and link refuse any
active payload whose linker version or hashes differ.

The first campaign slice is live. Smacker codec/string-xref reconstruction has
seven ordinary functions exact (nine source-associated bodies including `/GX`
helpers); `GetMissionObjectCount` is exact through the Bute config-serde calls
and the retail strings `Scenario\\GlobalMap.reg`, `Mission%d`, and
`MissionObjects`; and `lpDD` is an exact ordinary BSS identity. The three Bute
callee bodies are deliberately located stubs and remain work, not claimed
matches. The ported verification harness passes all 431 controls in the pinned
shell (five environment-dependent controls skip).

The vtable catalog joins two independent executable witnesses: 417 tables from
relocated text-pointer runs split by RTTI/code vptr references, plus eight
`GetRuntimeClass` tables whose first relocation site was absent from the
recovered stream. Of the 425 exact tables, 74 have a unique exact symbol+extent
definition in the pinned VC5 SP2 MFC archive. The other 347 are explicitly
`unresolved`; four more tables have retail-duplicate class spellings and are
therefore also withheld from static attribution. Unresolved rows become
`primary` only when reconstructed source earns the class/virtuality claim.
