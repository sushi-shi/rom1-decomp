---
name: wall-identifier
description: Classify a Rom1 matching WALL before spending effort on it. When a reconstruction plateaus below 100% and no spelling obviously closes it, name WHICH cl 5.0 decision diverged - inline/call-set, control flow, register/schedule, or masked/referent - and route to the lever for that class. Start with `rom1 walls diagnose <rva>`. Use when a function is stuck, when triaging plateaus, when asked "why won't this match" or "what kind of wall is this". Complements `matcher` (reconstructs) and `permute` (breaks proven codegen residue); this one DIAGNOSES.
---

# wall-identifier — classify the wall before fighting it

The selected cl 5.0 payload is a deterministic function: `bytes = f(preprocessed TU,
flags)`. Retail came out of the same `f` from real source, so every function is
reducible in principle — the job is finding which *input* differs. The unit of
reproduction is the **whole TU**, not the function: some residue is TU-global
front-end state that no local body edit can reach, but matching the TU context
can. Classify first; each class has a different lever and two of the four are
not permute problems at all.

## Start here

`rom1 walls diagnose <rva>` — classifies the residual from the same base/target
pair objdiff scores (no recompile) and routes it in the order below. The manual
equivalents, when you need the evidence itself:

- `rom1 sema match <unit|rva>` — current % vs best-ever (is there proven headroom?)
- `rom1 walls diagnose <rva> --asm` — normalized base/target pair, first
  divergence class, call/branch/return counts, and the first 60 instructions
  from each side
- `rom1 walls semdiff <rva>` — operand, FP-opcode, constant, and ordered
  referent comparison over that normalized pair
- `rom1 sema disasm <rva> --blocks` — annotated retail-only basic-block view;
  pairwise `--diff` and `--branches` flags are not implemented
- `rom1 verify assert-relocs <rva>` — the actual referent set, unmasked

## The four classes, in routing order

Do not call a wall class N while class N-1 still diverges.

`diagnose` classifies the primary body. A 100% primary row is not structural
proof: the command explicitly routes exact owners to `rom1.audit.eh_band`
because C1 state topology, cleanup targets, and synthetic receiver homes live in
separate scored records (`CKeyedList::AddNode`, `CFaderMesh::~CFaderMesh`, and
`ResetWorldState` are the controls).

| class | deciding signal | lever |
|---|---|---|
| **inline / call-set** | out-of-line CALL multiset differs | body completeness / inline budget — see below |
| **control flow** | block, branch, or ret COUNTS differ | source construct — structural matcher work, except the proven value-factoring case below |
| **register / schedule** | counts and branch sequence agree; operand order, spills, coloring differ | classified `rom1 permute state|variants` experiments |
| **masked / referent** | masked diff rc 0 but score < 100 | referent identity — labeling work, not codegen |

### inline / call-set

`/O2` on cl 5.0 is `/Ob1`: an unmarked function is NEVER auto-inlined, and an
`inline`-marked one is expanded under a per-CALLER budget that is measured and
modeled — `docs/patterns/inline-budget-emits-ool-comdat.md` re-validated the
sibling HoMM3 formula (`budget = clamp(2*cb(caller), 1000, 35000)`, free below
cb 0x28, nested expansions split the remainder) on our compiler, including where
the two compilers diverge (cl 5.0 has no VC6 S=14 cliff). Consequences:

- `rom1 walls diagnose` reads i386 `calll` instructions first, then the COFF
  REL32 callee multiset when instruction counts agree. This stage was inert
  before 2026-08-14 because it accepted only mnemonic `call`; the integration
  control in `rom1.match.gate_selftest` prevents that regression.
- The class name is deliberately **inline / call-set**, not “inline budget.” A
  call-count difference can also be duplicated or merged call-carrying exit
  tails (`StartUpPrompt`), and an equal-count callee substitution can be a wrong
  identity. Name the differing sites before choosing the budget lever.
- A count-only delta of a direct callee that remains present on both sides is
  reported as `REPEATED-SITE DELTA`. That does not distinguish a per-site inline
  decision from a duplicated/cross-jumped call tail. Locate the named sites and
  check the retail jumps before touching inline budget; `WireTileSwitchLogic` is
  the negative control (eight `StepArrivalDrop` sites in source, seven retail
  relocations because two tails merge).

- A missing inline expansion usually means the CALLER's body is incomplete —
  budget follows statement mass. Finish the caller before touching the callee.
- `llvm-nm build/objdiff/base/*.obj | grep <mangled>` screens which TUs emit a
  COMDAT; compare against retail's placement.
- Depth-2 declines, the one live `inline_depth` pragma, and a genuine cl 5.0
  wrong-code drop are catalogued: `inline-depth-two-declines-in-the-largest-caller.md`,
  `msvc5-inline-depth-zero-is-the-only-live-lever.md`,
  `ob1-budget-drops-the-inlined-dtor-and-the-return.md`.
- Never land a forcing device (PMF ref, dllexport, artificial caller) to
  materialize a COMDAT — `ob1-inline-budget-divergence.md`.

### control flow

A count mismatch is a reconstruction problem. cl 5.0's exit-merging has exactly
three source-selected regimes (separate returns / `goto fail` / `||`-collapse):
`goto-fail-shares-one-exit-block.md` is the master entry;
`dup-exit-means-a-shared-goto-label.md`, `while-not-do-while-keeps-the-inline-return.md`,
`do-while-duplicates-the-leading-call.md`, `void-vs-bool-return-epilogue-split.md`,
`backward-goto-sinks-its-target-region.md` cover the common shapes.
Screen candidates tree-wide with `python -m rom1.audit.exit_merge_sieve --dup`.

Two narrow exceptions are proven. On `CSBI_StatzTabGruntBar::Update` 0xea6c0, if the
first real divergence is an earlier register rotation and every extra edge is confined
to the two returns of an inlined value-only accessor, register availability can decide
whether global optimization factors the caller tail. That produces a branch-count delta
downstream of coloring with no authored CFG difference. Require the complete signature:
same source guards, call set, constants and ordered referents; only the accessor-return
tail is duplicated; and source-shaped result/receiver/scope controls are byte-flat. See
`docs/patterns/range-guarded-array-get-is-an-inline-accessor.md`.

`CSBI_ImageSet::SetupImage` 0xe72f0 is the return-count twin: its first divergence is
the instruction-zero host/`this` register rotation, and only later does retail give the
`key == NULL` edge a direct epilogue because key is already zero in EAX (4 returns versus
base 3). Require the same call, branch, ordered-referent, guard, store and inlined-accessor
structure; host-first order is independently proved by the retail argument load. A nested
positive gate is byte-flat, separate guards are worse, and owner-first is a false score win
because it reverses the retail argument-test order. This is not permission
to relabel an ordinary branch mismatch from counts alone—follow the first divergence.

### register / schedule

Reached by elimination only. This is the classified permuter's domain — banked
by MAX, never retained probe declarations. Two proven TU-global effects reach residue no
body edit can: mixed-KIND declaration probes
(`tu-state-probe-family-decides-reachability.md` — a flat sweep is evidence
about the probe, not the function) and the declaration-count window
(`declaration-count-window-steers-regalloc.md`). Probes are diagnostics: bank
the MAX, then delete them. Caution: one misplaced register op can mean the TYPE
is wrong (a member array modeled as scalars, a lost aggregate) — re-check the
model before permuting. Reading rule: `zero-register-compare-is-against-zero.md`.

### masked / referent

Objdiff reloc scoring is strict (target name/address, pointed-to data, DIR32
addends all participate), and the masked diff by construction cannot show a
wrong callee. If `--diff` returns rc 0 while the score sits below 100, the
divergence is referent identity: audit with `rom1 verify assert-relocs`, fix the labeling /
identity model, and do not grind permute on it.

## What does NOT transfer from HoMM3

The HoMM3 `wall-identifier` doctrine (this file's ancestor) is VC6-specific in
its mechanics. Do not use here without re-proving on cl 5.0:

- every `homm3 vc6 *` command (different repo, different compiler);
- the VC6 register-allocator model (preference order, first-fit by creation
  order) — nothing in this tree validates it for cl 5.0; hypothesis only;
- `il-diff` / C1XX IL capture — the cl 5.0 recipe is PROVEN
  (`/d1il<prefix>` capture, `/d2il<prefix>` feed; normalization rules and the
  probe-kind handle-stride table in `build/il-probe/REPORT.md` and the
  quantified section of `tu-state-probe-family-decides-reachability.md`), but
  the production `rom1 sema il-diff` verb is not built yet;
- `/Ob2` semantics and the S=14 save-gate cliff (cl 5.0 is `/Ob1`, no cliff).

A lever proven here goes in `docs/patterns/` + `INDEX.md` with the A/B evidence.
A reproducibly bounded residue remains visible through the derived inventory,
the current report/MAX ledger, and its valid `@early-stop` marker. Do not create
or revive a hand-kept wall ledger. Walls get broken, not hidden: bound a residue
only after the classified search stalls, and keep reusable mechanisms in the
pattern index rather than in reconstruction-history comments.
