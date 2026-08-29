# Rage of Mages 1 decompilation setup plan

Status: environment implemented; compiler-selection gate awaiting SP1/SP2 media,
2026-08-29

The project now has the pinned Gruntz-shaped environment, executable-native
retail censuses, relocation-manifest Vostok path, static-library comparison,
and vendor-header preparation. The remaining pre-campaign gate is the exact
SP1-versus-SP2 compiler servicing decision.

## What exists now

The separate repository now contains the Gruntz-shaped flake, CLI, scripts,
unit/config schemas, include/vendor roots, delinker, matching graph, and test
suite. The former investigation toolbox remains available as
`nix develop .#inventory`.

`src/` is intentionally empty: the exact compiler gate must be resolved before
the first translation unit is compiled. The authoritative retail layer already
contains FPO extents/frame metadata, strings, imports, PE/debug/section facts,
and recovered relocation sites.

The workspace contains roughly 58 GiB of source material and extracted data.
The raw and extracted corpora remain outside Git. The useful tracked inventory
already includes binary manifests, PE/toolchain summaries, imports, FPO maps,
radare2 function candidates, vtables, virtual methods, runtime classes, message
maps, cross-build tables, and media/archive listings.

Inventory output is a discovery aid. Its function boundaries, compiler labels,
and class names must be promoted through reviewed project evidence before they
become build truth.

## Locked retail baseline

The locked byte-matching target is:

```text
inventory/bin/rom1-engine-ru-buka-5ba821f3.exe
SHA-256  5ba821f37356d2da0e1eb907de28b2708714d6e2604b5caef3daf4284b9af7d3
Size     1,979,392 bytes
```

It is the Russian Buka `Hello__0` build dated 1998-09-09. The English and
Polish releases in the inventory corroborate the same engine bytes. The GOG
`942e9...` executable is useful as a clean runnable control but is not the
matching target.

Known target properties:

| Property | Value |
| --- | --- |
| Machine/subsystem | i386, Windows GUI |
| Image base | `0x00400000` |
| Image size | `0x00239000` |
| Entry RVA | `0x00156950` |
| Sections | `.text`, `.rdata`, `.data`, `.idata`, `.rsrc` |
| Linker header | 5.02 |
| Debug record | NB10, `c:\\allods.102\\Hello__0\\Allods.pdb`, age 11 |
| Base relocations | stripped; directory zero; no `.reloc` |

Current discovery counts include about 6,659 radare2 function candidates, 4,384
FPO records, roughly 1,390 EH-bearing functions, 117 MFC runtime classes, 358
paired vtables, and 114 class groupings. The FPO count and full records are now
canonical; the remaining heuristic counts are discovery evidence.

The working compiler hypothesis is Microsoft Visual C++ 5-era optimized C/C++,
static CRT/MFC, exception handling where required, frame-pointer omission in
many functions, no incremental linking, and little or no game-class C++ RTTI.
The exact compiler binary and each complete TU flag profile remain unproven.

## End-state layout

The bootstrap produced the familiar Gruntz-shaped repository:

```text
.
├── .agents/                 current matching skill/doctrine
├── .githooks/               staged-source formatting hook
├── config/
│   ├── retail/              authoritative function/data census
│   ├── units.toml           full-profile TU declarations
│   ├── match_baseline.tsv   unit/function score ratchets
│   ├── link_order.tsv
│   ├── link_bands.tsv
│   ├── reloc_referents.tsv
│   ├── gruntz_parity.tsv    exhaustive import/divergence ledger
│   └── ...                  same provider/review channels as Gruntz
├── docs/                    build, process, compiler, and evidence doctrine
├── include/
│   └── rva.h
├── nix/                     pinned package support and unchanged patches
├── scripts/
│   ├── rom1/                mechanically namespaced Gruntz package
│   └── ...                  toolchain/Wine builders
├── src/                     reconstructed source only
├── tests/                   if present in the pinned Gruntz layout
├── inventory/               discovery evidence, selected tracked reports
├── flake.nix
├── flake.lock
└── AGENTS.md
```

`config/retail/relocs.tsv` lives under `retail/` alongside the function and data
censuses and is passed directly to Vostok as `--reloc-manifest`.

`build/` remains generated and ignored. Raw game/media inputs remain ignored and
are addressed by verified hash, not committed.

## Phase 0: freeze provenance without losing current work

Deliverables:

1. Record the current index and inventory manifest before changing the flake.
2. Verify the target's size and SHA-256 from the local binary.
3. Record the Gruntz upstream URL, full commit ID, and canonical file manifest.
4. Add the parity contract and this plan.
5. Decide which inventory summaries are durable evidence and which bulky or
   reproducible outputs remain ignored.
6. Make a small baseline commit before the infrastructure transplant.

Gate:

- No existing staged file is lost or silently rewritten.
- The target can be reproduced by provenance plus SHA-256, while no retail
  executable is added to Git.
- `git status` contains only intentionally classified paths.

The baseline commit is a user-visible repository action and should be made only
when the owner asks for it. The working tree can be prepared and verified
without committing.

## Phase 1: exact Gruntz infrastructure transplant

Import from the pinned Git object, never the dirty local Gruntz checkout.

Work:

1. Generate the upstream file/hash manifest and initial
   `config/gruntz_parity.tsv`.
2. Copy every `exact` file byte-for-byte.
3. Generate every `rename` file using only the declared substitution table.
4. Bootstrap empty/header-only `target` config channels in their original
   schemas.
5. Preserve the existing investigation package set as
   `nix develop .#inventory`.
6. Make `default` and `build` the same Gruntz-equivalent shell; add the separate
   Gruntz-equivalent `play` shell.
7. Import the complete self-test/negative-control suite before adding RoM facts.
8. Import contributor doctrine and adjust examples/names only where classified.

Acceptance checks:

- `nix flake check --no-build` passes.
- `nix develop --command rom1 --help` exposes the same canonicalized command and
  option tree as the pinned `gruntz --help`.
- The resolved package versions, shell variables, hook behavior, wrapper root
  resolution, Wine registry inputs, and build/play prefix split match.
- Canonicalized script hashes, Python AST/import topology, and verification test
  rosters match the pin.
- A generated empty/bootstrap Ninja graph has the same rules, pools, aliases,
  default, stamps, `restat`, and write-if-changed behavior.
- Every import, rename, target file, seam, and exclusion is in the parity ledger.
- Every imported negative control still fails for its intended violation.

No matching starts until this phase is green. That prevents early convenience
changes from becoming permanent RoM1 quirks.

## Phase 2: retail preflight

Two target questions must be answered before Vostok output or compiler scores
can be trusted.

### 2A. Compiler and flag calibration

Build a witness panel covering C and C++, framed and FPO code, EH and non-EH
code, switch lowering, static initialization, MFC thunks/message maps, RTTI
where present, floating point, and small/large functions.

For each witness, record:

- exact retail RVA and proved extent;
- raw bytes and relevant relocatable operands;
- compiler package hash;
- complete named flag profile;
- assembly deltas and disqualifying signatures;
- result across multiple witnesses, not one lucky function.

Test the exact Gruntz VC5 SP3 package first. Compare `/Oy` and EH/RTTI profile
variants as full profiles. If linker/compiler fingerprints and witness bytes
consistently reject SP3, construct a precisely pinned VC5 alternative through
the same release pipeline and classify only the payload change as a seam.

Gate:

- At least one coherent compiler identity/profile family explains the witness
  panel better than the alternatives.
- The conclusion has byte evidence and a negative/control contrast.
- Unknown TU-level differences remain explicit; no global `/GR` or `/GX`
  assumption is promoted from inventory prose.

### 2B. Vostok relocation manifest

Use the local Vostok delinker's existing recovery path. Do not construct a new
scanner or synthesize a `.reloc` section.

The exact generator is tracked as `scripts/find_relocs.py`, imported from the
local Vostok commit `912a0aca03f3e7e188ba2fc057dab00ff081c4bb`. It is standalone Python 3,
uses `llvm-objdump`, and emits the native Vostok `--reloc-manifest` schema:

```text
site_rva	kind
0x1003	dir32
...
```

The initial default sweep is complete and stored at
`config/retail/relocs.tsv`: 32,454 kept DIR32 sites, 4,373 candidates rejected
by the generator's default `unmapped,data/code-isolated` filter, 32,457 lines,
and SHA-256
`6080243236d478ba0df2b5b2b0dced13874f1d6f3b02a03bae6db6062ba5c3e7`.

Bootstrap work:

1. Import `find_relocs.py` byte-for-byte from its local Vostok commit and pin its
   source identity in the parity ledger.
2. Backport Vostok's native `--reloc-manifest` parser/consumer and its tests onto
   the Gruntz Vostok base, retaining all eight Gruntz patches.
3. Add a regeneration wrapper that writes a candidate under `build/`, reports
   per-channel yield, compares it with the tracked manifest, and replaces the
   manifest only on an explicit write action.
4. Use reviewed inclusion/exclusion inputs only if target evidence proves a
   generic-sweep false negative or false positive.
5. Pass the unchanged retail executable plus
   `--reloc-manifest config/retail/relocs.tsv` to the normal delink rule.
6. Run Vostok's `--validate` generator mode against the closest suitable local
   non-stripped PE and preserve the channel precision/recall report as method
   calibration.

Gate:

- The retail executable is never rewritten and retains its known SHA-256.
- The manifest has the exact two-column Vostok header, only `dir32` rows,
  unique/in-range site RVAs, and deterministic ascending output.
- A no-manifest fixture fails on a stripped PE; the clean manifest fixture
  restores its DIR32 relocation; malformed header/kind/duplicate/out-of-range
  fixtures fail.
- Re-running the generator either reproduces the tracked manifest or reports a
  reviewed inclusion/exclusion delta; it cannot silently lose an admitted site.
- The Gruntz-based Vostok build consumes the manifest directly and delinks the
  original fixed-base PE.

The manifest is generated retail evidence. Individual rows are not manually
retyped or copied from another build.

## Phase 3: canonical census and model bootstrap

Convert discovery artifacts into Gruntz-schema evidence:

1. Re-decode the executable linearly and recursively with PE section boundaries,
   entrypoints, imports, FPO, EH, XCU, MFC tables, cross-references, and recovered
   relocations.
2. Establish exact function starts/extents and populate
   `config/retail/functions.tsv`. Record conflicts instead of choosing the most
   convenient disassembler answer.
3. Establish owned data starts/extents and populate
   `config/retail/data.tsv` plus vtable/compiler-generated/provider channels.
4. Fingerprint CRT, MFC, and other static-library functions against the exact
   compiler archives; record confidence and provenance in the unchanged provider
   schema.
5. Seed link bands and TU order from FPO/EH/XCU/static-library/section evidence.
   RoM1 has no known incremental ILT, so order uncertainty stays explicit.
6. Add the first source/header skeleton, `include/rva.h`, unit profiles, claims,
   and model inputs.

Gate:

- Retail censuses have deterministic generation/review reports and no duplicate
  ownership.
- Provider rows resolve to known census entries and do not overlap illegally.
- Labels generate from the single authoritative model.
- Claims, bindings, and violations regenerate without hand-edited build output.
- Every enabled gate has a non-vacuity control.

The initial census does not need every symbol to have a human name. It does need
stable identities and exact evidence-backed boundaries wherever claimed.

## Phase 4: first end-to-end vertical match

Choose one small leaf function only after the census and compiler witness panel
are trustworthy. Prefer a function with:

- an exact FPO or otherwise independently proved extent;
- no ambiguous tail merge or neighboring ownership;
- few or no unresolved global-data referents;
- a simple calling convention and no opaque EH funclet;
- a byte pattern present in corroborating builds or an identified library
  archive, when available.

Run it through the complete path:

```text
source + units.toml
  -> VC5 object
  -> source claims
  -> bindings/violations
  -> synthesized PDB/manifests
  -> Vostok named target object
  -> paired normalized objects
  -> objdiff report
  -> sema/raw-referent inspection
  -> verification
  -> manual baseline bank
```

Gate:

- Rebuilding from a clean `build/` reproduces the same generated graph and
  reports.
- Raw and normalized comparisons agree on what normalization changed.
- The function reaches a genuine, explainable result; no masked similarity,
  assembly injection, binary patching, or fake relocation steers it.
- Banking refuses unstaged build-input changes and updates the same
  current/best/historical/fingerprint fields as Gruntz.
- At least one deliberately damaged claim, referent, source hash, and baseline
  fixture fails the expected gate.

This vertical slice is the bootstrap milestone. It proves the environment, not
just the compiler invocation.

## Phase 5: grow by evidence, not by tooling variants

Expand from leaf functions to neighboring functions and then coherent TUs while
keeping the Gruntz process unchanged:

1. Work in recovered link order where evidence is strongest.
2. Promote exact addresses to claims only with proved extents.
3. Recover types, calling conventions, data ownership, static initializers,
   vtables, EH state, and compiler-generated artifacts as whole-TU constraints.
4. Treat layout/register/inlining differences as compiler-entropy problems and
   inspect raw disassembly plus referents before changing semantics.
5. Ratchet function and TU best/historical scores; never lower the recorded
   floor to accept a regression.
6. Turn on the same verification tiers in the same order as their inputs become
   non-vacuous.
7. Keep uncertain rows explicit and reviewed rather than adding parallel maps.

TU closure means all owned code/data/compiler artifacts and boundary/referent
checks are exact, not merely that every named function has a high fuzzy score.

## Phase 6: candidate link and runtime

Only after the object-level path is stable:

1. Recover target resource inputs and generate `build/gen/allods.res` through
   the transplanted resource command.
2. Recover library identity/order and link flags from PE/import/static-library
   evidence.
3. Build the opt-in `ALLODS.candidate.EXE` and map using the same candidate-link
   architecture.
4. Construct the separate play prefix with target registry, resolution, CD/data,
   and runtime-DLL inputs.
5. Use the byte-identical regional releases and the GOG build as runtime controls
   without changing the matching target.

Gate:

- Object matching remains independent of candidate-link success.
- Resources, import surface, section layout, entrypoint, and link map differences
  are reported explicitly.
- The play prefix is separate from the compiler prefix and reproducible from
  declared runtime inputs.
- Runtime success never substitutes for byte-match evidence.

## First implementation sequence

The smallest safe series of changes is:

1. baseline/provenance files and ignore review;
2. pinned Gruntz manifest plus parity verifier;
3. exact/renamed Python package and self-tests;
4. exact Nix pins, patches, shell wrapper, toolchain, and Wine construction;
5. explicit `inventory` shell carrying the present toolbox;
6. empty-schema configuration and graph emission;
7. compiler witness harness;
8. Vostok relocation-manifest integration, regeneration check, and negative controls;
9. authoritative census/model seed;
10. first complete one-function vertical slice.

Each change should be independently reviewable. The project does not proceed to
the next numbered item while parity or negative-control checks for the current
item are red.

## Decisions deliberately left evidence-driven

The following are not setup preferences and will not be guessed:

- whether the target compiler is exactly the Gruntz SP3 payload or an earlier
  VC5 payload;
- the final complete flag profiles and their TU allocation;
- future reviewed inclusions/exclusions to the generated relocation-site manifest;
- the authoritative function/data census and ownership boundaries;
- CRT/MFC/third-party library versions and archive providers;
- TU/link order in the absence of an incremental-link ILT;
- resource script, link flags, library order, and runtime/CD layout;
- which Gruntz domain-specific codec, REZ, lineage, or oracle adjuncts have a
  true RoM1 counterpart.

They will use the same Gruntz schemas and process once evidence exists. Until
then, an explicit empty/unknown state is preferable to a familiar-looking but
false default.
