---
name: matcher
description: Reconstruct and byte-match Rom1 C++ functions, translation units, classes, globals, and referents against retail ALLODS.EXE with the executable-selected MSVC 5.0 servicing payload. Use for function matching, low historical-MAX work, TU reconstruction, stub completion, class/type recovery, vtable or calling-convention recovery, relocation/referent correction, data modeling, and diagnosing a plateau before using the permuter.
---

# Rom1 matcher

Recover the original source structure that explains retail bytes. Correct
classes, types, ownership, control flow, storage, calls, and referents outrank a
temporary score. The objective is per-function historical MAX fuzzy = 100%.

## Establish the environment

1. Work in the pinned `nix develop` environment.
2. Confirm `config/compiler.toml` is selected. The SP3 bootstrap is rejected by
   retail's linker stamp and must never produce campaign objects.
3. Verify `vostok-delinker` and `objdiff-cli` resolve to the flake outputs when
   tool provenance is uncertain.
4. DATA extents come from the current TU through pylibclang. A full build
   refreshes `structs.json` before layout audits.
5. Treat `ninja 0.0s` as no verification. Rebuild the affected object before
   interpreting a result.
6. Never run, launch, replay, or capture the game. Do not use the Ghidra
   decompiler on `ALLODS.EXE`; use static assembly, xrefs, RTTI, vtables, data,
   and relocations.

## Choose work by historical MAX

- Work the lowest `hist_pct` rows first from `rom1 walls inventory`. A
  reproducibly bounded `@early-stop` remains in that derived queue; there is no
  hand-kept exclusion ledger.
- `hist_pct` is the campaign objective. Current fuzzy, current exact count, and
  aggregate fuzzy are navigation signals, not acceptance gates.
- `best_pct` belongs to the current per-function source fingerprint. A source
  edit may reset it; `hist_pct` preserves the all-time proof.
- Do not revisit a function whose historical MAX is 100%. Do not investigate an
  unrelated current-score dip when the MAX gate remains green.

## Reconstruct before steering

For each target:

1. Read its source claim, retail disassembly, callers, callees, strings, class
   hierarchy, vtable slots, and data references.
2. Establish the real owner TU, signature, calling convention, class identity,
   member layout, local entities, control flow, inline boundaries, constants,
   and ordered referents.
3. Implement the cleanest evidence-backed C++ shape.
4. Build incrementally and compare from the first genuine divergence. Inspect
   both candidate and retail assembly; fuzzy diff alone is insufficient.
5. Audit raw constants and ordered relocations. Objdiff scores target
   name/address, pointed-to data, and absolute DIR32 addends; use the linked-image
   referent audit for aliases, indirect calls, and final placement.
6. Iterate on a source-level cause: type or signedness, aggregate identity,
   lifetime/scope, condition polarity, loop form, tail sharing, declaration
   order, calling convention, or inline/out-of-line shape.
7. Use compiler-state search only after semantics and CFG are established.

Prefer semantic tools over lexical guesses. Use `rom1 sema xref` for call
identity, `rom1 sema class` or `vtable_hierarchy` for polymorphism, and
`rom1 sema disasm` views for code shape. RVA proximity and names alone do not
prove ownership.

## Classify the first divergence

Route a plateau in this order:

1. **Inline/call set:** compare out-of-line callees and ordered relocations. A
   missing or extra call is usually an inline-boundary or incomplete-body issue.
2. **CFG:** compare block, conditional-branch, and return counts. A branch-count
   mismatch is structural. Matching symbolic branch sequences narrow the
   residue to instruction selection, lifetime, scheduling, or allocation.
3. **Registers/frame:** compare entity creation order, live ranges, stack
   extents, saved registers, partial-register widths, and spill placement.
4. **Masked cosmetic:** prove raw instruction bytes and referents before calling
   a relocation-name difference harmless.

Do not label a low-score function a register wall while its call set or CFG is
still different.

## Model real source entities

- Give each class one canonical shared definition. Never create a `.cpp`-local
  view, layout shell, or fake base to make an access compile.
- Recover an uncertain receiver from both directions: callers, allocation and
  storage sites, callees, mangled signatures, vptr stores, RTTI, vtable slots,
  and member offsets. Use `@identity-TODO` only after the applicable evidence
  genuinely dead-ends.
- Express access through typed members. Raw offset casts, offset macros, casts of
  `this`, and arithmetic such as `*(static_cast<i32*>(p) + N)` are modeling
  defects, not solutions.
- Treat casts as symptoms. Retype the member or canonical class so placeholder
  casts disappear. Keep only conversions proven authentic at an SDK boundary,
  numeric conversion, heterogeneous container, or pointer/DWORD storage seam.
- Use real MFC and Win32 umbrella headers. Do not hand-roll platform typedefs,
  imports, or calling conventions.
- Use typed enums for proven domains and magic values. Enumerate only evidenced
  values. Retyping a function parameter or return changes MSVC mangling, so do
  it only when the retail signature supports it.
- Use semantic names. Do not introduce address-derived identifiers, compiler
  ordinals, or contextless stack names such as `local_10`.
- Treat adjacent scalars as a possible aggregate, not a conclusion. Prove
  `RECT`/`CRect`, `Coord`/`POINT`, strings, arrays, or records from complete-
  object calls, copies, field order, serialization, and storage extents. Do not
  split one retail object into overlapping globals or invent an aggregate for a
  score change.

## Recover vtables mechanically

Use the generated slot map; never hand-pad a vtable.

- `inherited`: declare nothing.
- `override`: declare the real method with `OVERRIDE`.
- `new`: declare the real method as plain `virtual`.

Never add dummy virtuals. One class has one real `??_7`. Absence of RTTI does not
prove a class is non-polymorphic because RTTI is module-scoped. A manual vptr
stamp is transitional reconstruction debt, not original source.

## Preserve data and annotation truth

- A datum is a real definition with `DATA(rva)`; `DATA_SYMBOL` is retired.
- A `DATA_COMPGEN` pin is last-resort: only for a datum the automatic oracles
  cannot identify (an ambiguous string payload, an FP slot with no
  reloc-corroborated referrer). Oracle-covered pins are removable noise; the
  header-inline COFF COMMONs live in `config/retail/compiler-generated-data.tsv`.
  Never bind compiler emission ordinals as semantic names; a `$E` helper is
  pinned at its owner with `RVA_DYNINIT`.
- `DATA(...)` identifies and audits storage; it does not force linker placement.
- Do not infer initialized-data correctness from aggregate objdiff data or from
  synthesized target sections. Keep `.bss` separate from initialized data.
- Do not model an interior address as independent overlapping storage. Refine
  the owner and access its real field or element.
- Never add source padding to fit a final-image gap.

## Use walls and permutation correctly

Use `rom1 permute state|variants` only when the body is complete and the call
set, CFG, types, constants, and referents are credible. Classify the wall first
with the project `wall-identifier` skill (`rom1 walls diagnose <rva>`); every lever
it does not list as cl 5.0-proven must be re-proved here before use.

- Use source permutations and TU-state changes as disposable A/B experiments.
- Never retain unused includes, declarations, fake locals, volatile carriers,
  manual `STATE` probes, or contorted spellings to steer codegen.
- State experiments are rarely justified below 90%; fix structure first.
- If unchanged function source reaches exact under a disposable TU state, bank
  MAX while exact, remove the perturbation, rebuild, and retain the historical
  proof.
- Stop grinding once controlled evidence bounds a residue. Keep the state in
  the derived report/MAX ledger and use `@early-stop` only when the body is
  complete; record reusable mechanisms in `docs/patterns/`, not in a hand-kept
  wall ledger or reconstruction-history C++ comments.

`@early-stop` is permitted only for a complete reconstruction with a reproducible
bounded residue. It never excuses missing logic, wrong referents, or an unresolved
identity.

## Verify and hand off

Before committing:

1. Recheck the target's branch structure, raw constants, and ordered
   relocations/referents.
2. Run `rom1 format` only on the intended tree; never format `vendor/`.
3. Stage only the focused source and documentation before the full build so a
   new MAX is banked against the intended fingerprint.
4. Run full `rom1 build`.
5. Require every gate green and `git diff --check` clean.
6. Commit source, focused durable documentation, and the relevant
   `config/match_baseline.tsv` updates; never commit generated build state.

Report the historical-MAX change, the structural correction, evidence and
negative controls, raw referent verdict, remaining bounded wall, full-build
result, and commit.
