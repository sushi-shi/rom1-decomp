"""rom1.walls.jccscan - the CONDITION-CODE sieve.

A conditional branch's mnemonic IS the source comparison operator, and it is
the one operand class objdiff never masks: `je` versus `jl` versus `jb` is a
different question about the same two values.  So a function whose base and
target hold DIFFERENT MULTISETS of condition codes is making a different
comparison somewhere, and that is a source fact, not a schedule coin.

Three readings, in descending strength:

  SIGNED    ours `jl` where retail has `jb` (or jle/jbe, jg/ja, jge/jae) in
            equal numbers.  A signedness slip: one side compares the loop
            guard or index as int and the other as unsigned.  This one is a
            defect, not a spelling - the two disagree for half the domain.
  OPERATOR  one side holds equality codes (je/jne) where the other holds
            ordered ones (jl/jle/jg/jge/...).  Usually a `switch` written as
            an `||` chain: cl folds clustered `case` labels into range tests
            (`cmp 4 / jl def; cmp 5 / jle arm; cmp 8 / jne def` for {4,5,8})
            and emits three `cmp/je` for the chain.
  POLARITY  the same codes but transposed counts (ours +N je, retail +N jne).
            An arm-order or guard-polarity difference; see
            merged-call-arms-expose-the-if-else-order.md and
            allocate-check-then-body-is-the-then-block.md.

COMPLEMENT FOLDING is what makes the third reading usable.  `je` against `jne`,
`jl` against `jge`, `jle` against `jg` are one branch asked the other way, which
at source level is an arm order far more often than a different predicate.  So
the surpluses are cancelled pairwise FIRST and the verdict is taken on what is
LEFT: a row that folds to nothing is pure polarity, and a row with residue is
holding a comparison the other side has not got.  The fold also demotes rows the
raw multiset over-reads - `CBattlezMapConfig::ValidateUnitPath` 0x29b40 and
`CTriggerMgr::SpawnGrunt` 0x7c110 each read OPERATOR on a bare je/jne plus jle/jg
surplus and are two arm orders, nothing more.

WHAT IT CANNOT SEE.  Equal multisets prove nothing: two `je` can still test
different things.  It counts codes, not operands.  And a branch cl folded away
entirely (a constant-folded guard) leaves no code to count, so a genuinely
missing comparison reads as a plain surplus on the other side.

NOR IS A ONE-BRANCH RESIDUE PROOF OF A SOURCE DIFFERENCE.  Eight
`CButeMgr::Set*` rows have reached 100.00 EXACT on the source now in the tree
(best = hist = 100 at an unchanged hash) and every one of them CURRENTLY sits at
82-96 showing retail hold one `je` we do not - a branch count moves under TU
composition alone.  Read the residue as a lead, then check the ledger.

THE REGION RULE, corrected twice on 2026-08-23 and in BOTH directions.  A switch
table and its padding decode as instructions, and that payload was the sieve's
whole false-positive population - `CPlay::LoadCursorSprites` 0xd0120 read as
three retail-only `js` that were all table bytes.  Cutting at the last `ret` is
wrong twice over:

  * it does not reliably remove the DATA - a table byte 0xc3 decodes as `ret`,
    and in `CRom1Mgr::HandleCommand` 0x862f0 (seven tables) that phantom
    `ret` re-admitted ~450 lines of payload and read the row as OPERATOR
    d=187 when the code is POLARITY d=8;
  * it discards real CODE - cl places cold blocks AFTER the last `ret`, each
    entered by a forward branch and leaving by a `jmp` back into the body. The
    cut threw away 5524 base / 6147 target instructions over the todo queue,
    531/599 of them condition codes, and the discarded count differs between
    the sides on 41 rows (`CGrunt::StepArrivalDrop` loses 18 instructions on
    ours and 535, holding 55 codes, on retail's).

So the region is bounded from BOTH ends.  The data boundary is stated by the
code itself: a switch dispatch is `mov cl,BYTE PTR [eax+0xTTTT]` /
`jmp DWORD PTR [ecx*4+0xTTTT]` carrying a relocation to the function's OWN
symbol, and the lowest such 0xTTTT is where the data starts - past it 0x862f0
holds zero external referents and zero real calls, i.e. it is entirely data.
Below that boundary the region is everything up to the last `ret` PLUS every
later run that starts at an intra-function branch target and ends at its
terminator, because nothing ever branches to a byte index table.

    rom1 walls jccscan [--todo] [--unit U] [--below N] [--limit N] [--json]
    rom1 walls jccscan --flips             rank by the first flip's jump distance
    rom1 walls jccscan <rva|name> ...      one row, every site listed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

from rom1.walls import check_unit
from rom1.walls.semdiff import pair_lines

#: every x86 conditional branch cl 5.0 emits, canonical spelling
CC = ("je", "jne", "jl", "jle", "jg", "jge", "jb", "jbe", "ja", "jae",
      "js", "jns", "jo", "jno", "jp", "jnp")

#: signed code <-> its unsigned counterpart on the same relation
SIGNED = {"jl": "jb", "jle": "jbe", "jg": "ja", "jge": "jae",
          "jb": "jl", "jbe": "jle", "ja": "jg", "jae": "jge"}

EQ = {"je", "jne"}
ORD = {"jl", "jle", "jg", "jge", "jb", "jbe", "ja", "jae"}

#: code <-> the code that tests the NEGATION of the same question
COMPLEMENT = {"je": "jne", "jl": "jge", "jle": "jg", "jb": "jae",
              "jbe": "ja", "js": "jns", "jo": "jno", "jp": "jnp"}
COMPLEMENT.update({v: k for k, v in COMPLEMENT.items()})


def fold_complements(ours: dict, retail: dict):
    """Cancel each `jcc`/`jncc` pair across the two sides and return the
    flips plus what is LEFT.

    A complement pair is one branch asking the same question the other way,
    which at source level is an arm order (`if (x) A else B` written the
    other way round) far more often than a different predicate.  Cancelling
    them first is what makes the residue readable: a row that folds to
    nothing is pure polarity, and a row that does not is holding a
    comparison the other side has not got."""
    ours, retail = dict(ours), dict(retail)
    flips = []
    for k in list(ours):
        c = COMPLEMENT.get(k)
        if c and retail.get(c):
            n = min(ours[k], retail[c])
            flips.append((k, c, n))
            ours[k] -= n
            retail[c] -= n
    return (flips,
            {k: v for k, v in ours.items() if v},
            {k: v for k, v in retail.items() if v})


#: a switch dispatch reading its own table: the displacement is the table base
TABLE = re.compile(r"^(?:jmp|mov)\b.*\[[^]]*\+0x([0-9a-f]{3,})\]")
#: a branch and its target - a cold block is ENTERED, a byte table never is
TARGET = re.compile(r"^(?:j\w+|loop\w*)\s+(0x[0-9a-f]+)$")
TERMINATOR = re.compile(r"^(?:ret|jmp)\b")


def code_region(lines, self_name: str = ""):
    """The instruction stream with the trailing DATA removed - and only that.

    Bounded from both ends, because cutting at the last `ret` alone is wrong in
    both directions (see the module docstring for the two measurements).

    First the DATA boundary, which the code states positively: a self-referent
    `jmp [reg*4+0xTTTT]` / `mov r8,BYTE PTR [reg+0xTTTT]` is a dispatch reading
    its own table, so the lowest such base is where the function's data starts.
    That is a stronger claim than "nothing branches here" and it removes the
    0xc3-decodes-as-`ret` case outright.

    Then, below that boundary, keep the cold blocks: everything up to the last
    `ret`, plus every later run entered at an intra-function branch target and
    ending at its terminator.
    """
    base = min((int(m.group(1), 16) for x in lines if x.ref == self_name
                for m in [TABLE.match(x.asm)] if m), default=None)
    if base is not None:
        lines = [x for x in lines if x.addr < base]
    last = max((i for i, x in enumerate(lines) if x.asm.startswith("ret")),
               default=len(lines) - 1)
    targets = {int(m.group(1), 16) for x in lines
               if x.ref is None and (m := TARGET.match(x.asm))}
    out, live = lines[:last + 1], False
    for ln in lines[last + 1:]:
        if ln.addr in targets:
            live = True
        if live:
            out.append(ln)
            if TERMINATOR.match(ln.asm):
                live = False
    return out


def codes(lines, self_name: str = "") -> Counter:
    return Counter(x.asm.split()[0] for x in code_region(lines, self_name)
                   if x.asm.split()[0] in CC)


def classify(ours: Counter, retail: Counter) -> dict | None:
    if ours == retail:
        return None
    so = {k: ours[k] - retail.get(k, 0) for k in ours if ours[k] > retail.get(k, 0)}
    sr = {k: retail[k] - ours.get(k, 0) for k in retail if retail[k] > ours.get(k, 0)}
    flips, ro, rr = fold_complements(so, sr)
    signed = [(k, SIGNED[k]) for k in ro
              if k in SIGNED and SIGNED[k] in rr and ro[k] == rr[SIGNED[k]]]
    if signed:
        kind = "SIGNED"
    elif (set(ro) & EQ and set(rr) & ORD) or (set(ro) & ORD and set(rr) & EQ):
        kind = "OPERATOR"
    else:
        kind = "POLARITY"
    return {"kind": kind, "ours_extra": so, "retail_extra": sr,
            "flips": flips, "residue_ours": ro, "residue_retail": rr,
            "balanced": sum(so.values()) == sum(sr.values()),
            "signed": signed, "delta": sum(so.values()) + sum(sr.values())}


def scan_one(rva: str) -> dict:
    binding, base, target = pair_lines(rva)
    rec = classify(codes(base, binding.name), codes(target, binding.name))
    return {"agree": rec is None, **(rec or {})}


#: an intra-function branch, whose displacement objdiff masks in the DIFF but
#: which is right here in the decode
BRANCH = re.compile(r"^(j\w+) 0x([0-9a-f]+)$")


def branch_seq(lines):
    out = []
    for x in lines:
        m = BRANCH.match(x.asm)
        if m and m.group(1) in CC:
            out.append((m.group(1), x.addr, int(m.group(2), 16)))
    return out


def jumps_an_epilogue(lines, addr, tgt) -> bool:
    """Does the span this branch jumps OVER contain a `ret`?

    Over a `ret` the branch is skipping a duplicated EXIT; over anything else
    it is stepping past a block cl merely placed there, which is layout.  Note
    the exit can be duplicated without the source asking for it - cl also
    clones a shared `goto` target - so this locates the question, it does not
    answer it.

    Only ever ask this of the NEARER of the two jumps.  A long forward branch
    crosses most of the function and will clear a `ret` whatever it is doing,
    so testing the far side reports a hit on every row."""
    if not (addr < tgt):
        return False
    return any(x.asm.startswith("ret") for x in lines if addr < x.addr < tgt)


def first_flip(base, target, self_name):
    """The first position where the two branch sequences disagree, with each
    side's jump DISTANCE and whether that jump clears an epilogue.

    The distance is the reading, not the mnemonic.  `retail jumps FAR where we
    jump NEAR OVER A RET` says retail branched away to a shared tail while we
    laid a duplicated epilogue inline - the steerable direction of
    guard-skip-loop-not-early-return.md.  The reverse is the tail-merge wall.
    A big distance gap with NO `ret` in the skipped span is neither; it is a
    block cl placed between the branch and its target.

    Not decided by this one site alone either way: cl also chooses WHICH of
    several identical returns stays inline, so check the neighbouring guards
    (see that pattern's over-application note, UseEquippedToolAt 0x6dae0).

    THE POSITIONAL WALK BELOW IS SOUND, AND RE-ALIGNING IT IS WORSE.  Zipping
    two sequences by index normally drifts on the first insert or delete, but
    `--flips` only ever ranks rows `classify` called BALANCED, and balanced
    surpluses means equal branch COUNTS (checked: 23 of 23).  A plain
    insert/delete therefore cannot occur here, only a compensated pair.  Both
    difflib re-alignments were measured and both invent divergences the
    disassembly refutes: keyed on the bare condition code the 16-symbol
    alphabet is under-determined and it put LoadStateRecord 0x555e0's surplus
    at branch #0 where the two sides are instruction-identical; keyed on the
    preceding opcodes it is over-determined and any scheduling change breaks
    the anchor, so it read Sync 0x1084d0, StepDefenderBehavior 0xee800 and
    WireTileSwitchLogic 0x6c130 as `extra branch` rows when all three have
    hand-verified corresponding pairs at the site this walk reports."""
    o, t = code_region(base, self_name), code_region(target, self_name)
    ob, rb = branch_seq(o), branch_seq(t)
    for k in range(min(len(ob), len(rb))):
        if ob[k][0] != rb[k][0]:
            om, oa, ot = ob[k]
            rm, ra, rt = rb[k]
            # Only the NEARER jump's span is a meaningful test: a long forward
            # branch passes over most of the function and will find a `ret`
            # whatever it is doing.
            near_ours = abs(ot - oa) <= abs(rt - ra)
            return (k, ob[k], rb[k],
                    near_ours and jumps_an_epilogue(o, oa, ot),
                    (not near_ours) and jumps_an_epilogue(t, ra, rt))
    return None


def flips(token: str, ctx: int = 4) -> None:
    binding, base, target = pair_lines(token)
    o, t = code_region(base, binding.name), code_region(target, binding.name)
    hit = first_flip(base, target, binding.name)
    print(f"== {binding.unit}/{binding.name}")
    if hit is None:
        print("   branch sequences agree in mnemonic order")
        return
    k, (om, oa, ot), (rm, ra, rt), oep, rep = hit
    od, rd = abs(ot - oa), abs(rt - ra)
    lean = ("retail jumps FAR, we jump NEAR" if rd > od + 40 else
            "we jump FAR, retail jumps NEAR" if od > rd + 40 else
            "same distance - a plain arm order")
    over = ("  ours clears a RET, so WE hold the duplicated exit - steerable"
            " only if the source states that exit more than once" if oep else
            "  retail clears a RET, so RETAIL holds the duplicated exit:"
            " the tail-merge wall" if rep else
            "  neither clears a RET: block placement, not an exit count")
    print(f"   branch #{k}: ours {om} +0x{od:x}   retail {rm} +0x{rd:x}   ({lean})")
    print(f"  {over}")
    for nm, lines, addr in (("ours  ", o, oa), ("retail", t, ra)):
        i = next(j for j, x in enumerate(lines) if x.addr == addr)
        for j in range(max(0, i - ctx), min(len(lines), i + ctx)):
            print(f"   {nm} {'>>' if j == i else '  '}{lines[j].addr:04x} "
                  f"{lines[j].asm}")
        print()


def detail(token: str, limit: int = 12) -> None:
    binding, base, target = pair_lines(token)
    ours = codes(base, binding.name)
    retail = codes(target, binding.name)
    rec = classify(ours, retail)
    print(f"== {binding.unit}/{binding.name}")
    if rec is None:
        print("   condition-code multisets AGREE (this sieve has nothing to say;"
              " equal counts are not proof)")
        return
    print(f"   {rec['kind']}   ours {dict(ours)}")
    print(f"   {'':8}retail {dict(retail)}")
    if rec["flips"]:
        print("   complement flips (arm order, or the predicate written the "
              "other way): "
              + ", ".join(f"ours {a} / retail {b}" + (f" x{n}" if n > 1 else "")
                          for a, b, n in rec["flips"]))
    if rec["residue_ours"] or rec["residue_retail"]:
        print(f"   residue after folding: ours {rec['residue_ours']} "
              f"retail {rec['residue_retail']}"
              "   <- a comparison one side has and the other has not")
    if rec["signed"]:
        print("   signed/unsigned pairs: "
              + ", ".join(f"ours {a} vs retail {b}" for a, b in rec["signed"]))
    want = set(rec["ours_extra"]) | set(rec["retail_extra"])
    for nm, lines in (("ours  ", base), ("retail", target)):
        region = code_region(lines, binding.name)
        sites = [i for i, x in enumerate(region) if x.asm.split()[0] in want]
        for i in sites[:limit]:
            ctx = " ; ".join(y.asm for y in region[max(0, i - 2):i + 1])
            print(f"   {nm} @{region[i].addr:04x}  {ctx}")
        if len(sites) > limit:
            print(f"   {nm} ... {len(sites) - limit} more site(s) "
                  f"(--limit to widen; a surplus spread over many sites is a"
                  f" whole-function polarity question, not one guard)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls jccscan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("rows", nargs="*", metavar="rva")
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--flips", action="store_true",
                    help="rank the BALANCED rows by the first flipped branch's "
                         "jump distance: retail FAR against ours NEAR is the "
                         "steerable direction")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.rows:
        for token in args.rows:
            (flips if args.flips else detail)(token, args.limit if not args.flips else 4)
        return 0

    from rom1.walls.inventory import build
    rows = build(check_unit(args.unit), args.below, args.todo)
    out = []
    for n, row in enumerate(rows, 1):
        rec = {k: row[k] for k in ("rva", "unit", "symbol", "cur", "hist_max")}
        try:
            rec.update(scan_one(row["rva"]))
            if args.flips and rec.get("balanced"):
                b, base, target = pair_lines(row["rva"])
                hit = first_flip(base, target, b.name)
                if hit:
                    k, (om, oa, ot), (rm, ra, rt), oep, rep = hit
                    rec["flip"] = {"n": k, "ours": om, "retail": rm,
                                   "ours_dist": abs(ot - oa),
                                   "retail_dist": abs(rt - ra),
                                   "ours_over_ret": oep, "retail_over_ret": rep}
        except BaseException as err:
            rec["error"] = str(err)[:110]
        out.append(rec)
        if not args.json and n % 100 == 0:
            print(f"  ... {n}/{len(rows)}", file=sys.stderr)

    if args.json:
        json.dump(out, sys.stdout)
        return 0

    hits = [r for r in out if r.get("agree") is False]
    if args.flips:
        rank = [r for r in hits if r.get("flip")]
        print(f"{len(rank)} balanced row(s) with a locatable first flip.")
        print("  ret> = the side whose near jump clears a RET, i.e. holds the"
              " DUPLICATED exit.")
        print("  ours is a CANDIDATE for guard-skip-loop-not-early-return.md -"
              " but only when the source really does state that exit twice.")
        print("  It also reads `ours` when cl duplicated a shared `goto` target"
              " the source states ONCE (StepMagicWandGruntBehavior 0xf8240), which is")
        print("  not steerable. Read the source before editing.")
        print("  retail is the tail-merge wall; '-' means neither, so the gap is"
              " block placement, not an exit count.")
        print(f"{'gap':>7} {'ret>':>6} {'rva':>10} {'cur':>6}  ours       retail"
              "     unit/symbol")
        for r in sorted(rank, key=lambda x: -(x["flip"]["retail_dist"]
                                              - x["flip"]["ours_dist"]))[:args.limit]:
            f = r["flip"]
            who = ("ours" if f["ours_over_ret"] else
                   "retail" if f["retail_over_ret"] else "-")
            print(f"{f['retail_dist'] - f['ours_dist']:7d} {who:>6} {r['rva']:>10} "
                  f"{r['cur']:6.2f}  {f['ours']:<4}+{f['ours_dist']:<5x} "
                  f"{f['retail']:<4}+{f['retail_dist']:<5x} "
                  f"{r['unit']}/{r['symbol'][:34]}")
        return 0
    by = Counter(r["kind"] for r in hits)
    print(f"rows read: {sum(1 for r in out if 'error' not in r)}"
          f"   (errors {sum(1 for r in out if 'error' in r)})")
    print(f"  condition-code multiset DIFFERS : {len(hits):4d}"
          f"   SIGNED {by['SIGNED']}  OPERATOR {by['OPERATOR']}"
          f"  POLARITY {by['POLARITY']}")
    print(f"  agree                           : "
          f"{sum(1 for r in out if r.get('agree')):4d}"
          f"   (agreement is NOT evidence - it counts codes, not operands)")
    print()
    order = {"SIGNED": 0, "OPERATOR": 1, "POLARITY": 2}
    for r in sorted(hits, key=lambda x: (order[x["kind"]], -x["delta"]))[:args.limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f} {r['kind']:<9} d={r['delta']:<3d} "
              f"ours+{r['ours_extra']} retail+{r['retail_extra']}  "
              f"{r['unit']}/{r['symbol'][:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
