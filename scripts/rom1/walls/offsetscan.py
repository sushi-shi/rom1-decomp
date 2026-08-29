"""rom1.walls.offsetscan - the MEMBER-OFFSET sieve.

A memory operand's displacement IS the field the source names.  objdiff does
not mask it, so `mov ecx,[ebx+0x64]` against our `mov ecx,[ebx+0x68]` is not a
schedule coin and not a register rotation: it is a DIFFERENT MEMBER, and every
run of the game reads the wrong dword.  That makes this, with `signscan`, one
of the two channels whose hits are CORRECTNESS defects rather than spellings.

The defect hides from every other reading.  The instruction is the same
instruction, in the same block, with the same mnemonic, the same operand shape
and the same relocation set; only four bits of the ModRM displacement differ.
`diagnose` reports it as "bytes first differ at +0xNNN" with the class
REGALLOC/SCHEDULING, which is exactly the verdict that makes a reader stop.

WHY IT IS FOUND BY ALIGNMENT AND NOT BY A CENSUS.  A displacement MULTISET
delta drowns: 0x10 and 0x68 are among the commonest offsets in the image, so
a real 4-site swap sits inside dozens of unrelated occurrences and any
threshold that admits it admits noise.  What is decisive is the SAME POSITION:
align the two instruction streams on a key that masks every operand cl is
free to choose - the registers (regalloc rotates them), the immediates, the
displacements themselves - and then read the displacements back at the
positions the alignment called EQUAL.  A mismatch there is one instruction
that both sides emit, doing the same thing, to a different field.

WHAT IS EXCLUDED, AND WHY:

  * frame-relative operands.  `[esp+N]` is a stack slot, and a slot number is
    an output of cl's allocator, not a source fact - `framescan` owns that
    question.  `[ebp+N]` is excluded ONLY when that side really set up a frame
    pointer (`push ebp / mov ebp,esp` in the prologue); /O2 omits it in 669 of
    671 retail bodies, and in a frameless body EBP is an ordinary value
    register, so `lea eax,[ebp+0x4]` is a heap field.  `frame_regs` (shared
    with `escapescan`) decides per side.
  * a line whose relocation IS its memory operand.  An absolute `ds:0x...`, a
    global folded into `[eax+<table>]`, a `$L` block address, the function's own
    index table decoding as junk: the displacement is a link-time address
    objdiff masks, the referent channel owns it, `assert-relocs` proves it.  A
    relocated line whose relocation is a separate IMMEDIATE is NOT excluded -
    see `reloc_owns_operand`.
  * the function's own switch/index table, which decodes as instructions -
    removed by `code_pair`'s byte-range filter, as `diagnose` removes it - and
    the indirect `jmp`/`call` through it, whose displacement is the table's
    link-time address.
  * a candidate whose two displacements are BOTH touched by BOTH sides inside
    the same aligned run.  Then the two accesses were merely SCHEDULED in a
    different order and the aligner paired them crosswise - storescan's
    channel.  This was the sieve's dominant false-positive population: one
    99.56% row produced 46 such pairs forming closed permutation cycles.  A
    wrong MEMBER, by contrast, is a field the other side never touches there.
  * a candidate within two instructions of the EDGE of its aligned run.  That
    is where the pairing slips: one side has an extra instruction and the tail
    walks off by one, so two unrelated accesses meet.  Three live rows read
    that way and every one was an extra instruction, not a different field.
    Counted apart from `short-run`, below.
  * a candidate in a run of 2*EDGE instructions or fewer.  Such a run has no
    interior at all, so the EDGE rule discards it wholesale; that is the
    different statement "nothing here can be corroborated", not "the pairing
    slipped at a boundary", and conflating the two told a reader a run had
    slipped when there was never a run.
  * an aligned pair whose BASE REGISTERS differ.  Two instructions indexing off
    different pointers are two different accesses the masked key happened to
    align; requiring the same base is what separates the reading from the
    alignment's own noise.  It bounds the sieve in exchange: a real wrong
    member whose base register rotated too does not reach the report.

WHAT THE SUPPRESSIONS THROW AWAY, measured 2026-08-23 by re-running the sweep
with each filter OFF and classifying all 6983 candidate pairs over 588 rows:

  frame     5204 pairs.  Structurally undecidable, not discarded evidence: the
            slot base moves between builds, and a stack STRUCT's field offset
            is folded into the same number, so `[esp+0x40]` against
            `[esp+0x44]` cannot be told from a wrong field of a local RECT.
            framescan owns it.
  order      757 pairs, of which 686 are per-field BALANCED - each side touches
            both displacements the same number of times in the run, which is
            what a permutation means.  Of the 71 unbalanced, only THREE show
            the wrong-member signature (ours favours one field, retail the
            other); all three were read against the disassembly
            (CFaderShape::ApplyInit +0x60/+0x64, CGrunt::
            LoadGruntCombatAnimations +0x17c/+0x180 twice) and every one is
            mirrored rematerialization of the same value.
  basereg    858 pairs.  The blind spot is real but not reachable: derive the
            register correspondence from the alignment itself (inside one run,
            ours `[ebx+D]` against retail `[esi+D]` for the same D witnesses
            ebx=esi there) and admit mismatches between corresponding
            registers, and the whole image yields SEVEN such pairs and ZERO
            live ones - even demanding a single witness.  A rotated base
            register travels with a wholesale regalloc divergence that leaves
            nothing to corroborate against.
  edge        75 pairs, 29 of them in runs of <= 2*EDGE.  That is why the two
            are now counted apart.  Every long-run case was read: they are the
            CSbiHlRow ctor divergence, the CGrunt ctor's interleaved clearing
            run, and lea-folded array bases.
  scaled       1 pair, and it was table junk.  Sound by construction: an
            operand whose only register is scaled has no object pointer, so its
            displacement cannot be a member offset.
  reloc       46 pairs.  This one WAS hiding a class: a relocation sits in
            exactly one operand, and `mov DWORD PTR [this+0x70],OFFSET
            ??_7CObject@@6B@` - the vptr stamp - keeps a real member offset in
            the memory operand while the relocation is the immediate.  A vptr
            stamped into the wrong subobject moves two bytes and no channel
            read them.  SPLIT rather than loosened: the suppression now asks
            which operand the relocation owns.  Admitting the immediate class
            adds zero rows to the live sweep, so the split is a closed blind
            spot, not new noise.

WHAT THE LIVE SWEEP IS WORTH.  All seven live rows of 2026-08-23 hand-read:
ONE genuine (`CStatusBarMgr::LoadRezMachineConfig`, an addressing SHAPE - a
cursor into the array where retail names the array - now EXACT and gone), and
six alignment SLIPS.  Coverage predicts a slip without excluding one:
`CProjectile::LoadProjectileSprites` reads as a 4-byte layout shift at 93.7%
coverage and both sides in fact use the same four offsets.  Read every row
against the disassembly before believing it.

THE READING THAT SETTLES A ROW is the whole-function displacement census, taken
with the base register IGNORED (it rotates).  Equal counts on every displacement
means the positional hit is a slip - `CWarlord`'s ctor is exactly that, 33 keys
identical and every store at the same byte address, off a one-instruction index
shift.  Two cautions, both measured: a census delta of +1/-1 on adjacent members
is usually mirrored rematerialization rather than a swap, and the census cannot
see through a folded base - `CGrunt::StepDiggerBehavior` reads `this->m_rect`
partly through `this` (+0x64/+0x68/+0x6c) and partly through a pointer to it,
which reads as three fields retail never touches and is the same four addresses.

WHAT IT STRUCTURALLY CANNOT SEE.  A wrong member whose offset happens to
coincide with the right one moves no byte.  A wrong member inside a block the
alignment could not match - an inline/call-set or CFG wall shifts the streams
far enough that whole regions read as `replace` - is dropped rather than
guessed at; the sieve reports how much of each side it could align, so a low
coverage figure is a warning that the reading is partial, not clean.  And an
aligned mismatch is a LEAD until the retail disassembly says which member the
displacement belongs to: two adjacent scalars of one class, or one class's
member against a base subobject's copy of the same pointer, look identical
here and only the class model separates them.

THE SHAPE THAT BUILT IT.  `CTriggerMgr::LoadTileArrivalFx` reached the goober
puddle through `CUserLogic::m_object` (+0x10) where retail uses
`CWapX::m_wwdObject` (+0x38) - `CGruntPuddle` derives from both and the two
members hold the same pointer, so nothing misbehaved - and read the gauge award
from +0x68 where retail reads +0x64.  That second one was a real bug:
`CGruntPuddle::Place` (byte-exact) homes its fourth argument at +0x64, and
`CTriggerMgr::PlacePuddle` passes `sprite->m_points` there with the same 25
default the caller primes, so the pickup credited the puddle's type id instead
of its points.  Five aligned displacement mismatches, no other signal.

    rom1 walls offsetscan [--todo] [--unit U] [--limit N] [--all] [--json]
    rom1 walls offsetscan <rva|name> ...   one row, every mismatch in context
    rom1 walls offsetscan --control        re-prove the verdict on the rows
                                             read by hand
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter

from rom1.walls import check_unit
from rom1.walls.escapescan import code_pair, frame_regs

#: one memory operand: an optional size prefix, a base register, an optional
#: scaled index, an optional displacement.  `ds:0x...` has no bracket and is
#: therefore not matched at all.
MEM = re.compile(r"\[(e[a-z]{2})(\*\d)?"
                 r"(?:\+(e[a-z]{2})(\*\d)?)?"
                 r"([+-]0x[0-9a-f]+)?\]")

REG = re.compile(r"\be[a-z]{2}\b|\b[a-d][lh]\b|\b[a-d]x\b|\b[sd]i\b|\b[sb]p\b")
IMM = re.compile(r"0x[0-9a-f]+")

#: an immediate operand OUTSIDE the brackets, which is where a relocation sits
#: when it is NOT the memory operand's displacement
OUTSIDE_IMM = re.compile(r"(?:^|,)\s*0x[0-9a-f]+\s*$")


def reloc_owns_operand(asm: str, ref: str, self_name: str | None) -> bool:
    """True when this line's relocation is the MEMORY operand's displacement.

    A relocation sits in exactly one operand, and which one decides whether the
    displacement means anything.  In `[eax+<g_table>]` or in the function's own
    index table decoding as junk, the displacement IS the masked link-time
    address and belongs to the referent channel.  In `mov DWORD PTR
    [this+0x70],OFFSET ??_7CObject@@6B@` - the vptr stamp - the relocation is
    the IMMEDIATE and `0x70` is a real member offset, so a stamp into the wrong
    subobject must reach the report.  An immediate outside the brackets is the
    discriminator; a line whose referent is the function ITSELF is its own
    table either way.
    """
    if self_name and ref == self_name:
        return True
    return OUTSIDE_IMM.search(asm) is None


def operand(asm: str) -> tuple[str, int] | None:
    """(base register, displacement) of this line's MEMBER operand, or None.

    An operand whose only register is SCALED (`[ecx*4+0x127c]`) is an array
    index off an absolute address - a jump table, a global - not a field of an
    object, and its displacement is a link-time address the referent channel
    owns.  Those leave here.
    """
    if asm.startswith(("jmp", "call")):
        return None
    m = MEM.search(asm)
    if not m or m.group(2):
        return None
    disp = m.group(5)
    return m.group(1), int(disp, 16) if disp else 0


def key(asm: str) -> str:
    """The instruction with everything cl is free to re-choose masked out:
    the registers, the immediates and the displacements.  What survives is
    the mnemonic and the operand SHAPE, which the source fixes."""
    return IMM.sub("I", REG.sub("R", asm))


def field_lines(lines, self_name: str | None = None) \
        -> list[tuple[str, tuple[str, int] | None]]:
    """Each instruction as (alignment key, member operand or None)."""
    frame = set(frame_regs(lines))
    out = []
    for ln in lines:
        # A relocation only disqualifies the displacement when the relocation
        # IS that displacement - a global, a jump/index table base, the
        # function's own table decoding as junk.  When it is a separate
        # immediate the displacement is a real member offset and is read.
        op = operand(ln.asm)
        if op and ln.ref and reloc_owns_operand(ln.asm, ln.ref, self_name):
            op = None
        if op and op[0] in frame:
            op = None
        out.append((key(ln.asm), op))
    return out


#: a permutation can also straddle a run boundary, so the run set is widened
#: by this many instructions on each side of it
MARGIN = 8

#: a mismatch this close to the edge of its aligned run is where the aligner
#: SLIPS - one side has an extra instruction and the pairing walks off by one
EDGE = 2


def _touched(side, lo: int, hi: int) -> set:
    """The member operands one side reads or writes inside one aligned run,
    widened by MARGIN so a permutation that straddles the boundary is still
    seen as one."""
    lo, hi = max(0, lo - MARGIN), min(len(side), hi + MARGIN)
    # DISPLACEMENTS only: the base register is precisely what regalloc rotates,
    # so keying the suppression on it would ask a question about allocation
    # instead of about which field the run touches.
    return {side[k][1][1] for k in range(lo, hi) if side[k][1]}


def mismatches(base, target, self_name: str | None = None) \
        -> tuple[list[dict], int, int, int, int, int]:
    """Aligned positions whose member displacements differ, how many
    instructions the alignment matched, and how many candidates were
    suppressed as an order swap, as a run too short to corroborate anything,
    or as an alignment slip at the edge of a longer run."""
    fb, ft = field_lines(base, self_name), field_lines(target, self_name)
    sm = difflib.SequenceMatcher(a=[k for k, _ in fb], b=[k for k, _ in ft],
                                 autojunk=False)
    out, aligned, swapped, edged, tiny = [], 0, 0, 0, 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            continue
        aligned += i2 - i1
        # A run of 2*EDGE or fewer instructions has no interior: EVERY position
        # in it is within EDGE of a boundary, so the rule below would discard it
        # wholesale.  That is a different statement - the run is too short to
        # corroborate anything - and it is counted apart so a reader is not told
        # a pairing "slipped at an edge" when there was never a run to slip in.
        short = (i2 - i1) <= 2 * EDGE
        ours_run, retail_run = _touched(fb, i1, i2), _touched(ft, j1, j2)
        for i, j in zip(range(i1, i2), range(j1, j2)):
            ob, ot = fb[i][1], ft[j][1]
            # The base register must AGREE.  Two aligned instructions indexing
            # off DIFFERENT pointers are two different accesses the masked key
            # happened to align, not one access to two fields; requiring the
            # same base is what separates the reading from the alignment's own
            # noise.  It also bounds the sieve: a real wrong member whose base
            # register rotated as well is invisible here.
            if not (ob and ot and ob[0] == ot[0] and ob[1] != ot[1]):
                continue
            # Both sides touch BOTH fields somewhere in the SAME aligned run:
            # the accesses were SCHEDULED in a different order and the aligner
            # paired them crosswise.  That is a store/load order question -
            # storescan's channel - not a wrong member, and a long store run
            # permutes far enough that a positional window cannot see it (46
            # such pairs in one 99.56% row, forming closed cycles).  A wrong
            # MEMBER shows as a field one side never touches in that run.
            if ot[1] in ours_run and ob[1] in retail_run:
                swapped += 1
                continue
            # An aligned run's EDGE is where the pairing slips: the side with
            # an extra instruction walks the whole tail off by one, and the two
            # unrelated accesses that meet there read as one wrong member.
            # Measured on three live rows (CVoiceManager::Clear,
            # CInGameIcon::PlaceAt, CRollingBall's ctor), every one an extra
            # instruction on our side rather than a different field.
            if min(i - i1, i2 - 1 - i, j - j1, j2 - 1 - j) < EDGE:
                if short:
                    tiny += 1
                else:
                    edged += 1
                continue
            out.append({"ours": base[i].asm, "retail": target[j].asm,
                        "ours_disp": ob[1], "retail_disp": ot[1],
                        "shape": fb[i][0]})
    return out, aligned, min(len(fb), len(ft)), swapped, edged, tiny


#: a run of this many mismatches sharing ONE masked instruction shape is a
#: SET question, not a positional one
RUN = 5


def kind(bad: list[dict]) -> str:
    """`run` when most mismatches share one masked instruction shape.

    A long run of literally identical instructions - `mov [esi+X],edi` with
    EDI zero, the ctor's field clearing - carries no information about which
    store pairs with which, so the alignment zips two lists and every pair
    reads as a mismatch.  The real question there is which FIELDS each side
    clears, a set difference; `field` rows are the ones where the mismatch is
    isolated and the position means something.
    """
    if not bad:
        return "clean"
    top = max(Counter(m["shape"] for m in bad).values())
    return "run" if top >= RUN else "field"


def scan_one(token: str) -> dict:
    binding, base, target = code_pair(token)
    bad, aligned, total, swapped, edged, tiny = \
        mismatches(base, target, binding.name)
    swaps: dict[str, int] = {}
    for m in bad:
        swaps[f"{m['ours_disp']:#x}->{m['retail_disp']:#x}"] = \
            swaps.get(f"{m['ours_disp']:#x}->{m['retail_disp']:#x}", 0) + 1
    return {"nbad": len(bad), "swaps": swaps, "sites": bad,
            "order_swaps": swapped, "edge_slips": edged, "short_runs": tiny,
            "kind": kind(bad),
            "coverage": round(100.0 * aligned / total, 1) if total else 0.0}


def scan(rows: list[dict], progress=None) -> list[dict]:
    out = []
    for n, row in enumerate(rows, 1):
        rec = {k: row[k] for k in ("rva", "unit", "symbol", "cur", "hist_max")}
        try:
            rec.update(scan_one(row["rva"]))
        except BaseException as err:
            rec["error"] = str(err)[:110]
        out.append(rec)
        if progress and n % 100 == 0:
            print(f"  ... {n}/{len(rows)}", file=progress)
    return out


def report(rows: list[dict], limit: int, show_all: bool) -> None:
    ok = [r for r in rows if "nbad" in r]
    hit = [r for r in ok if r["nbad"]]
    field = [r for r in hit if r["kind"] == "field"]
    print(f"paired rows read: {len(ok)}   (errors {len(rows) - len(ok)})")
    print(f"  an isolated member offset differs : {len(field):4d}")
    print(f"  a whole clearing/copy RUN differs : {len(hit) - len(field):4d}"
          f"   (a field SET question, read the two sets)")
    print(f"  clean                             : {len(ok) - len(hit):4d}")
    print()
    print("coverage = the share of the shorter side the alignment matched; a "
          "low figure means the streams diverge structurally and this reading "
          "is partial.")
    print(f"{'rva':>10} {'cur':>7} {'n':>4} {'cov':>6}  unit/symbol")
    for r in sorted(hit if not show_all else ok,
                    key=lambda x: (x["kind"] != "field", x["cur"]))[:limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f} {r['nbad']:4d} "
              f"{r['coverage']:5.1f}% {r['kind']:>5}  "
              f"{r['unit']}/{r['symbol'][:40]}")
        for swap, n in sorted(r["swaps"].items(), key=lambda kv: -kv[1]):
            print(f"{'':>12}{swap:<20} x{n}")


def detail(token: str) -> None:
    binding, base, target = code_pair(token)
    bad, aligned, total, swapped, edged, tiny = \
        mismatches(base, target, binding.name)
    cov = round(100.0 * aligned / total, 1) if total else 0.0
    print(f"== {binding.unit}/{binding.name}   aligned {aligned}/{total} "
          f"({cov}%)   suppressed: {swapped} order, {edged} run-edge, "
          f"{tiny} short-run")
    if not bad:
        print("   no aligned member offset differs")
    for m in bad:
        print(f"   ours   {m['ours']}")
        print(f"   retail {m['retail']}")


#: hand-verified rows, each re-derived from the disassembly.  A sieve nobody
#: has seen FIRE is a green light, not a check.
CONTROL = {
    "0x00075e90": (False,
                   "NEGATIVE: CTriggerMgr::LoadTileArrivalFx is the row that "
                   "built this sieve - it held +0x10 for CWapX::m_wwdObject "
                   "(+0x38) and +0x68 for the gauge award retail reads at "
                   "+0x64.  Both are fixed, so it must stay silent"),
}


def _hermetic() -> int:
    """The POSITIVE, kept as a fixture because the only live one is the row
    this sieve CLOSED.  These are the exact retail and base bytes of
    CTriggerMgr::LoadTileArrivalFx's puddle block; the end-to-end proof is
    stronger and is recorded in docs/patterns: the defect was re-introduced
    into the source, rebuilt, and the sweep named both displacements in one
    line each before the fix was restored."""
    from rom1.walls.semdiff import Line
    pad = ["nop"] * EDGE
    mk = lambda a: [Line(i * 4, t, None) for i, t in enumerate(pad + a + pad)]
    ours = mk(["mov ecx,DWORD PTR [ebx+0x68]", "push ecx", "call 0x0",
               "mov ebx,DWORD PTR [ebx+0x10]", "push ebx"])
    retail = mk(["mov edx,DWORD PTR [ebx+0x64]", "push edx", "call 0x0",
                 "mov ebx,DWORD PTR [ebx+0x38]", "push ebx"])
    got = {(m["ours_disp"], m["retail_disp"])
           for m in mismatches(ours, retail)[0]}
    want = {(0x68, 0x64), (0x10, 0x38)}
    ok = got == want
    print(f"{'FIRES ' if ok else 'BROKEN'} hermetic  "
          f"{'ok' if ok else f'got {got}, want {want}'}")
    print("      POSITIVE: the puddle block's own bytes - the gauge award at "
          "+0x68 for retail's +0x64, and CUserLogic::m_object (+0x10) for "
          "CWapX::m_wwdObject (+0x38)")
    return (0 if ok else 1) + _hermetic_reloc()


def _hermetic_reloc() -> int:
    """The relocated-IMMEDIATE positive and its NEGATIVE partner.

    `mov DWORD PTR [this+N],OFFSET ??_7X@@6B@` carries a relocation, and until
    2026-08-23 that alone dropped the line - so a vptr stamped into the wrong
    subobject moved two bytes and no channel read them.  The negative is the
    same suppression doing its real job: a global folded INTO the memory
    operand, where the displacement is the masked link-time address.
    """
    from rom1.walls.semdiff import Line
    pad = ["nop"] * (EDGE + 1)
    mk = lambda a, r: [Line(i * 4, t, r if i - len(pad) in (0,) else None)
                       for i, t in enumerate(pad + a + pad)]
    bad = 0

    stamp_o = mk(["mov DWORD PTR [esi+0x70],0x0", "mov eax,esi"], "??_7CObject@@6B@")
    stamp_r = mk(["mov DWORD PTR [esi+0x0],0x0", "mov eax,esi"], "??_7CObject@@6B@")
    got = {(m["ours_disp"], m["retail_disp"])
           for m in mismatches(stamp_o, stamp_r)[0]}
    ok = got == {(0x70, 0x0)}
    print(f"{'FIRES ' if ok else 'BROKEN'} hermetic-reloc-imm  "
          f"{'ok' if ok else f'got {got}, want {{(0x70, 0x0)}}'}")
    print("      POSITIVE: the relocation is the IMMEDIATE, so the vptr stamp's "
          "own displacement is a real member offset and must be read")
    bad += 0 if ok else 1

    folded_o = mk(["mov eax,DWORD PTR [esi+0x70]", "mov eax,esi"], "?g_table@@3PAHA")
    folded_r = mk(["mov eax,DWORD PTR [esi+0x0]", "mov eax,esi"], "?g_table@@3PAHA")
    n = len(mismatches(folded_o, folded_r)[0])
    print(f"{'SILENT' if n == 0 else 'BROKEN'} hermetic-reloc-mem  "
          f"{'ok' if n == 0 else f'{n} hit(s), want 0'}")
    print("      NEGATIVE: the relocation IS the memory operand, so the "
          "displacement is a masked link-time address the referent channel owns")
    return bad + (0 if n == 0 else 1)


def control() -> int:
    bad = _hermetic()
    for rva, (expect, why) in CONTROL.items():
        try:
            rec = scan_one(rva)
        except BaseException as err:
            print(f"FAIL {rva}: {err}")
            bad += 1
            continue
        fires = bool(rec["nbad"])
        ok = fires == expect
        print(f"{'FIRES ' if fires else 'SILENT'} {rva}  "
              f"{'ok' if ok else 'UNEXPECTED'}  {rec['swaps']}")
        print(f"      {why}")
        bad += 0 if ok else 1
    if bad:
        print("\na control changed verdict: the row was fixed or regressed, or "
              "the detector did - read it, then re-pick")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls offsetscan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("rows", nargs="*", metavar="rva",
                    help="adjudicate these rows instead of sweeping")
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--control", action="store_true",
                    help="re-prove the detector's verdict on hand-read rows")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.control:
        return control()
    if args.rows:
        for token in args.rows:
            detail(token)
        return 0
    from rom1.walls.inventory import build
    rows = build(check_unit(args.unit), args.below, args.todo)
    scanned = scan(rows, progress=None if args.json else sys.stderr)
    if args.json:
        json.dump(scanned, sys.stdout)
        return 0
    report(scanned, args.limit, args.all)
    return 0
