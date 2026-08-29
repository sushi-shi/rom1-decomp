"""rom1.walls - the wall-breaking slice: the remaining matching campaign.

    rom1 walls inventory        the derived worklist (report x Model x
                                  match_baseline) - ascending historical MAX
    rom1 walls abstractions     classify every sub-100 row by the semantic
                                  level to inspect before source-shape work
    rom1 walls diagnose <fn>    classify one wall from the normalized pair:
                                  referent -> inline/call-set -> cfg -> regalloc
    rom1 walls inline-model     the cl 5.0 inline-budget model. `--gap <rva>`
                                  names the call-set delta and reports the base
                                  obj's candidacy evidence. A defined COMDAT
                                  proves inline visibility; an undefined or
                                  absent symbol is ambiguous and needs source,
                                  /Ob0, or call-site-topology evidence.
                                  `--gap <spec.json>` quantifies the deficit
                                  once cb is known; --measure-cb titrates cb
                                  with the real compiler
    rom1 walls aggregate-copies rep-movs count sieve; a source/CFG lead,
                                  never proof until block merging is excluded
    rom1 walls aggdecl          AGGREGATE-VS-SCALAR DECLARATION sieve: per
                                  member pair (K, K+4), does each side store a
                                  whole-object COPY or two independent scalars.
                                  A disagreement names the direction we are
                                  wrong in. WALK/ARG sub-kinds separate the
                                  three shapes that look identical and are not
                                  an aggregate; `--control` re-proves the
                                  detector on all four fixtures
    rom1 walls uninitscan       CONDITIONALLY-UNINITIALIZED LOCAL sieve, via
                                  clang-cl over the clangd database: cl 5.0 has
                                  no flow-sensitive C4701 and is silent on the
                                  whole class. A hit inside a function already
                                  at 100% is FAITHFUL - the bytes are retail's,
                                  so the hole is retail's; the rest is the
                                  worklist. Blind to aggregate members, which
                                  `--control` re-proves
    rom1 walls framescan        stack-frame-size sieve: our `sub esp,N`
                                  against retail's, ranked by what survives
                                  masking the displacements a frame shift moves
    rom1 walls jccscan          CONDITION-CODE sieve: the branch mnemonic IS
                                  the source comparison operator and objdiff
                                  never masks it, so a differing multiset is a
                                  different comparison (SIGNED = a signedness
                                  defect, OPERATOR = switch-vs-|| chain,
                                  POLARITY = arm order)
    rom1 walls loopscan         loop-BODY-SIZE sieve: an instruction inside
                                  the loop on one side and outside it on the
                                  other runs N times instead of once, and a
                                  masked diff reads that as a schedule coin
    rom1 walls retscan          one-sided calling-convention sieve: retail's
                                  own `ret N` against our mangled name's
                                  stack-argument bytes. The stack complement of
                                  thisscan, which owns ECX: a dropped RECEIVER
                                  is invisible here and a dropped ARGUMENT is
                                  invisible there. --cdecl is the half `ret 0`
                                  cannot do - our declared __cdecl argument
                                  bytes against RETAIL's caller cleanup, still
                                  one-sided. --virtual runs the vtable-slot
                                  census over the same names
    rom1 walls signscan         ARITHMETIC signedness sieve, the complement of
                                  jccscan: cl lowers a division, modulo, shift
                                  or narrow load through different instructions
                                  per declared signedness, so `cdq`/`idiv`/`div`
                                  /one-operand `imul`/`mul` counts and a
                                  sar<->shr or movsx<->movzx swap name a TYPE.
                                  The only wall class that is a CORRECTNESS
                                  difference (--control fires it on a positive)
    rom1 walls offsetscan       MEMBER-OFFSET sieve: align the two streams on
                                  a key that masks the registers, immediates and
                                  displacements, then read the displacements
                                  back where the alignment said EQUAL.  Same
                                  instruction, same position, different field -
                                  a WRONG MEMBER, the other correctness channel
                                  beside signscan
    rom1 walls vptrscan         VPTR-STAMP census: which SUBOBJECT a ctor
                                  stamps a vtable into, and WHICH vtable. Read
                                  from the COFF bytes (a DIR32 in the imm32 of
                                  a `C7 /0` decodes backwards), because the
                                  positional sieves only see stamps their
                                  alignment paired and a wrong subobject offset
                                  moves two bytes. The third correctness
                                  channel beside signscan and offsetscan.
                                  `--slots` is the companion reading: which
                                  vtable SLOT each `call [reg+N]` dispatches
                                  through - the stamp says the object claims
                                  the right class, the slot says the call
                                  reaches the right method of it, and
                                  offsetscan drops every call/jmp line by
                                  construction
    rom1 walls aggscan          BY-VALUE AGGREGATE ARGUMENT sieve: cl 5.0
                                  hands a block wider than a register by
                                  opening a hole (`sub esp,N` + `mov reg,esp`
                                  + dword copies), so a hole retail opens and
                                  we never do says the callee's parameter is
                                  ONE object where we declared scalars. Keyed
                                  on the CALLEE over the whole image, which
                                  asks the signature question of every site at
                                  once (framescan owns the frame reservation)
    rom1 walls escapescan       ADDRESS-ESCAPE sieve (declined enregistration):
                                  retail materializing a frame address INTO a
                                  call we feed from a register says the source
                                  is missing an `&` or a whole local object.
                                  Keyed on the callee referent, because the raw
                                  `lea [esp+N]` count is rematerialization, not
                                  source
    rom1 walls reloadscan       the three DECLINED memory optimizations, one
                                  machine: a load retail repeats ACROSS a call
                                  (CSE declined - the source re-reads it), a
                                  load retail repeats INSIDE a loop (hoisting
                                  declined - aliasing or an escaped address),
                                  and an INDEX vs pointer-walk loop body
                                  (strength reduction declined - the induction
                                  variable is live after the loop)
    rom1 walls valuetemp        by-value struct temp sieve: retail's inlined
                                  accessor returns a pair BY VALUE and leaves the
                                  UNREAD half's store dead in the frame
                                  (--control re-proves the detector fires)
    rom1 walls residue          what the masked residual IS, once position
                                  and register-name differences are cancelled
                                  (arm-result temps, wrong constants/offsets)
    rom1 walls storescan        permuted-member-store-run sieve: the two
                                  sides store the same fields in a different
                                  ORDER, so the source transcribed C2's output
                                  (--values screens for a swapped CONSTANT)
    rom1 walls thisscan         dropped-receiver sieve: a member modelled as
                                  a free function has IDENTICAL callee bytes,
                                  so only a caller shows it - as a dead ECX
                                  load retail emits before the call and we do
                                  not (--inverse for the mirror). --retail is
                                  the stronger form: our side carries no
                                  information here, so retail's own call sites
                                  decide the row with no score and no pairing
    rom1 walls eh-frame         /GX frame-presence + unwind-state sieve,
                                  cause-tagged (inline/merge/state-flow/object)
    rom1 walls global-refs      global read-COUNT sieve (the cached-global
                                  bug class; --calibrate = detector-bug rate)
    rom1 walls semdiff <fn>     OPERAND-LEVEL adjudication of one pair:
                                  exclusive fp/disp/store/imm keys, plus the
                                  ordered referent sequence a masked diff
                                  structurally cannot show
    rom1 walls semsweep <tsv>   the same screen over a worklist range - one
                                  line per clean row, the exclusive keys and
                                  FP deltas for the rest
    rom1 walls ehactions <fn>   the /GX unwind ACTION sequence (object slot
                                  + dtor identity, in order) of one parent -
                                  a funclet COUNT delta is the ctor-inlining
                                  boundary, a differing action is a defect.
                                  --census does the whole sub-100 EH band,
                                  grouped by parent: the funclets pair BY
                                  CONSTRUCTION through the normalizer's
                                  canonical names, and most of the band is a
                                  second readout of its parent's frame.
                                  --census classifies the band; --shift reads
                                  the slot-shift group's displacement deltas
                                  and says whether each parent's objects moved
                                  as a unit or relative to each other
    rom1 walls calibrate        the REFLEXIVITY control the paired sieves
                                  lacked: framescan/loopscan/jccscan/storescan/
                                  residue over the EXACT rows, where every cell
                                  must be 0. It tests the REFERENT filters (the
                                  two objects are cl's and the delinker's, and
                                  their relocation tables differ even at
                                  100.00); it structurally CANNOT test whether
                                  a byte-keyed quantity is comparable between
                                  two different builds - that is equal here by
                                  construction
    rom1 walls stale-markers    @early-stop markers sitting on 100% bodies
    rom1 walls review           Codex's source-hash-scoped personal reviews
    rom1 walls recheck          re-measure the COUNT certifications a review
                                  states ("base/retail agree on 24 calls, 96
                                  branches, 64 relocs") against today's pair -
                                  a review that certifies counts is an
                                  assertion, and nothing re-ran it
    rom1 walls priors           BOTH prior-verdict stores for a worklist -
                                  the comment above the RVA() pin AND the
                                  review ledger row - screened before any A/B

The easy matches are drained; what remains of the matching objective IS the
walls. This package holds the instruments a matcher points at a classified
wall. What does NOT live here: blind permutation search (removed by ruling -
walls are broken by understood levers, not ground).  The worklist is derived
from the compare report every time.  The optional Codex review ledger records
only reviewer progress and invalidates each row when its source hash changes;
it is not evidence that a reconstruction is correct.

Input surface: the Model, the compare out-dir (report.json + normalized
objs), config/match_baseline.tsv, tool.objdump/tool.cl, delink.coffx (the
shared COFF topology reader). Read-only except inline-model's scratch
harness compiles under build/inline-model/.
"""

from __future__ import annotations

_SUBS = {"calibrate": "rom1.walls.calibrate",
         "inventory": "rom1.walls.inventory",
         "abstractions": "rom1.walls.abstractions",
         "diagnose": "rom1.walls.diagnose",
         "inline-model": "rom1.walls.inline_model",
         "aggregate-copies": "rom1.walls.aggregate_copies",
         "eh-frame": "rom1.walls.eh_frame",
         "framescan": "rom1.walls.framescan",
         "jccscan": "rom1.walls.jccscan",
         "loopscan": "rom1.walls.loopscan",
         "signscan": "rom1.walls.signscan",
         "offsetscan": "rom1.walls.offsetscan",
         "vptrscan": "rom1.walls.vptrscan",
         "aggscan": "rom1.walls.aggscan",
         "aggdecl": "rom1.walls.aggdecl",
         "uninitscan": "rom1.walls.uninitscan",
         "escapescan": "rom1.walls.escapescan",
         "reloadscan": "rom1.walls.reloadscan",
         "valuetemp": "rom1.walls.valuetemp",
         "residue": "rom1.walls.residue",
         "retscan": "rom1.walls.retscan",
         "storescan": "rom1.walls.storescan",
         "thisscan": "rom1.walls.thisscan",
         "global-refs": "rom1.walls.global_refs",
         "ehactions": "rom1.walls.ehactions",
         "semdiff": "rom1.walls.semdiff",
         "semsweep": "rom1.walls.semdiff",
         "stale-markers": "rom1.walls.stale_markers",
         "priors": "rom1.walls.priors",
         "recheck": "rom1.walls.recheck",
         "review": "rom1.walls.reviews"}


def check_unit(unit: str | None) -> str | None:
    """`--unit` filters answer 0/none for a name nobody has - which reads as a
    clean result rather than a typo. Reject an unknown unit here instead."""
    if unit is None:
        return None
    from rom1.manifest import units as manifest_units
    known = {u["unit"] for u in manifest_units()}
    if unit in known:
        return unit
    import difflib
    import sys
    near = difflib.get_close_matches(unit, sorted(known), n=3)
    print(f"[walls] unknown unit {unit!r} - not in config/units.toml"
          + (f" (did you mean: {', '.join(near)}?)" if near else "")
          + "\n        `rom1 sema map units` lists the units that claim rows",
          file=sys.stderr)
    raise SystemExit(2)


def main(argv=None) -> int:
    import importlib
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    if argv[0] not in _SUBS:
        print(f"rom1 walls: unknown verb {argv[0]!r} (have: "
              f"{', '.join(_SUBS)})", file=sys.stderr)
        return 2
    mod = importlib.import_module(_SUBS[argv[0]])
    sys.argv = [f"rom1 walls {argv[0]}", *argv[1:]]
    entry = mod.sweep_main if argv[0] == "semsweep" else mod.main
    return entry(argv[1:])
