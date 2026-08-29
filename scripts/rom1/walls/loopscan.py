"""rom1.walls.loopscan - the loop-BODY-SIZE sieve over the worklist.

An instruction that sits INSIDE a loop on one side and OUTSIDE it on the
other is not a schedule coin: it runs N times instead of once.  That is a
source difference - a declaration placed inside the body instead of above
it, an invariant we recompute, a member re-read every iteration - and it is
the shape `FindProcessByName` turned out to be, where a 548-byte
`MODULEENTRY32 me = {0};` was re-zeroed on every step of the walk.

A masked diff cannot show it.  Masking address operands cancels branch
DISPLACEMENTS, so the loop boundary itself is invisible, and the same
instruction on the two sides of that boundary reads as a pair of moved
lines - the exact texture of a scheduling coin.  This measures the boundary
directly: for every backward branch, the instruction span from its target
down to the branch.

    base span > target span     we left something inside retail hoisted out
    base span < target span     retail keeps something inside that we
                                hoisted, folded into an expression, or a
                                different loop entirely
    loop COUNT differs          one side unrolled, cross-jumped two bodies
                                into one, or lost a `while` to a `do`-guard

Loops are paired by (branch mnemonic, the ordered call referents in the
body), so an inlined callee moves a loop into the `unpaired` column rather
than silently aligning it against its neighbour.

A one-instruction delta is NOT noise here: `rep stos`, `rep movs` and a
`call` each carry an unbounded amount of work in a single instruction, and
the FindProcessByName hoist was exactly two.

WHAT IT CANNOT SEE.  It counts instructions, not work or bytes, so it is
blind to a body of the same LENGTH holding different instructions (we
hoisted A, retail hoisted B), and to a hoist whose instruction was already
absent from our reconstruction.  A loop cl fully unrolled has no backward
branch and leaves the census entirely.  Nothing here attributes a delta to
a source statement - it says which loop to read, not what to write.

    rom1 walls loopscan [--todo] [--unit U] [--limit N] [--all] [--json]
    rom1 walls loopscan <rva|name> ...      one row, every loop listed

Cost: one objdump decode per side per row, so the sweep is a few minutes
over the full queue.  `walls diagnose` and `walls semdiff` adjudicate the
rows it flags.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher

from rom1.walls import check_unit
from rom1.walls.semdiff import pair_lines

#: a conditional/unconditional branch or a `loop`; `call` is deliberately out
BRANCH = re.compile(r"^(j[a-z]+|loop[a-z]*)\s")
TARGET = re.compile(r"^[a-z]+\s+(0x[0-9a-f]+)$")


def loops(lines, self_name: str = "") -> list[dict]:
    """Every backward branch, with the instruction span it closes.

    A branch carrying a relocation leaves the function (a tail jump into
    another symbol), so only unrelocated - or self-referential - branch
    targets close a loop.
    """
    at = {ln.addr: i for i, ln in enumerate(lines)}
    out = []
    for i, ln in enumerate(lines):
        if not BRANCH.match(ln.asm):
            continue
        if ln.ref and ln.ref != self_name:
            continue
        m = TARGET.match(ln.asm)
        if not m:
            continue
        tgt = int(m.group(1), 16)
        if tgt >= ln.addr or tgt not in at:
            continue
        j = at[tgt]
        body = lines[j:i]
        out.append({"head": j, "branch": i, "span": i - j,
                    "br": ln.asm.split()[0],
                    "head_asm": lines[j].asm,
                    "calls": tuple(b.ref for b in body
                                   if b.asm.startswith("call") and b.ref),
                    "mnem": Counter(b.asm.split()[0] for b in body)})
    return out


def key(lp) -> tuple:
    return (lp["br"], lp["calls"])


def pair(lb: list[dict], lt: list[dict]):
    """[(ours, retail)] for loops the anchoring proved are the same loop,
    plus the count of loops it refused to pair."""
    sm = SequenceMatcher(None, [key(x) for x in lb], [key(x) for x in lt],
                         autojunk=False)
    pairs, unpaired = [], 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            pairs.extend(zip(lb[i1:i2], lt[j1:j2]))
        elif (i2 - i1) == (j2 - j1) and all(
                lb[i1 + k]["br"] == lt[j1 + k]["br"] for k in range(i2 - i1)):
            pairs.extend(zip(lb[i1:i2], lt[j1:j2]))
        else:
            unpaired += max(i2 - i1, j2 - j1)
    return pairs, unpaired


def extra(a: Counter, b: Counter) -> list[str]:
    """The mnemonics one body holds that the other does not, biggest first."""
    d = {k: a[k] - b.get(k, 0) for k in a if a[k] > b.get(k, 0)}
    return [f"{k}x{v}" if v > 1 else k
            for k, v in sorted(d.items(), key=lambda kv: -kv[1])]


def scan_one(rva: str) -> dict:
    binding, base, target = pair_lines(rva)
    lb, lt = loops(base, binding.name), loops(target, binding.name)
    pairs, unpaired = pair(lb, lt)
    diffs = []
    for ours, theirs in pairs:
        if ours["span"] == theirs["span"]:
            continue
        diffs.append({"br": ours["br"], "head": ours["head_asm"][:34],
                      "base_span": ours["span"], "tgt_span": theirs["span"],
                      "ours_extra": extra(ours["mnem"], theirs["mnem"])[:6],
                      "tgt_extra": extra(theirs["mnem"], ours["mnem"])[:6]})
    worst = max((abs(d["base_span"] - d["tgt_span"]) for d in diffs),
                default=0)
    return {"base_loops": len(lb), "tgt_loops": len(lt),
            "unpaired": unpaired, "diffs": diffs, "worst": worst,
            "fat": sum(1 for d in diffs if d["base_span"] > d["tgt_span"])}


def scan(rows: list[dict], progress=None) -> list[dict]:
    out = []
    for n, row in enumerate(rows, 1):
        rec = {k: row[k] for k in ("rva", "unit", "symbol", "cur", "hist_max")}
        try:
            rec.update(scan_one(row["rva"]))
        except BaseException as err:              # SystemExit from the locator
            rec["error"] = str(err)[:110]
        out.append(rec)
        if progress and n % 100 == 0:
            print(f"  ... {n}/{len(rows)}", file=progress)
    return out


def report(rows: list[dict], limit: int, show_all: bool) -> None:
    ok = [r for r in rows if "diffs" in r]
    count = [r for r in ok if r["base_loops"] != r["tgt_loops"]]
    sized = [r for r in ok if r["diffs"]]
    fat = [r for r in sized if r["fat"]]
    print(f"paired rows read: {len(ok)}   (errors {len(rows) - len(ok)})")
    print(f"  loop COUNT differs        : {len(count):4d}")
    print(f"  a paired loop's BODY SIZE : {len(sized):4d}  "
          f"(ours FATTER on at least one loop: {len(fat)})")
    print(f"  clean                     : {len(ok) - len(count) - len(sized):4d}"
          f"   (rows holding an unpairable loop: "
          f"{sum(1 for r in ok if r['unpaired'])})")
    print()
    shown = ok if show_all else sized
    print(f"{'rva':>10} {'cur':>7} {'loops':>9} {'worst':>6}  unit/symbol")
    for r in sorted(shown, key=lambda x: -x["worst"])[:limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f} "
              f"{r['base_loops']:4d}/{r['tgt_loops']:<4d} {r['worst']:6d}  "
              f"{r['unit']}/{r['symbol'][:54]}")
        for d in r["diffs"][:4]:
            print(f"{'':>19}body {d['base_span']:4d} vs retail "
                  f"{d['tgt_span']:<4d} [{d['br']} <- {d['head']}]"
                  + (f"  ours+{','.join(d['ours_extra'])}"
                     if d["ours_extra"] else "")
                  + (f"  retail+{','.join(d['tgt_extra'])}"
                     if d["tgt_extra"] else ""))


def detail(token: str) -> None:
    binding, base, target = pair_lines(token)
    lb, lt = loops(base, binding.name), loops(target, binding.name)
    print(f"== {binding.unit}/{binding.name}")
    print(f"   loops: ours {len(lb)}, retail {len(lt)}")
    pairs, unpaired = pair(lb, lt)
    for ours, theirs in pairs:
        flag = "  <-- BODY" if ours["span"] != theirs["span"] else ""
        print(f"   {ours['br']:<6} body {ours['span']:4d} vs retail "
              f"{theirs['span']:<4d}  head `{ours['head_asm'][:38]}`{flag}")
        if ours["span"] != theirs["span"]:
            for label, mn in (("ours  ", extra(ours["mnem"], theirs["mnem"])),
                              ("retail", extra(theirs["mnem"], ours["mnem"]))):
                if mn:
                    print(f"        {label} holds: {', '.join(mn[:10])}")
    if unpaired:
        print(f"   {unpaired} loop(s) the anchoring refused to pair "
              f"(the call sets differ - read `walls diagnose` first)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls loopscan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("rows", nargs="*", metavar="rva",
                    help="adjudicate these rows instead of sweeping")
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true",
                    help="the campaign queue rather than every sub-100 row")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--all", action="store_true",
                    help="list the rows whose loop bodies agree too")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

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


if __name__ == "__main__":
    raise SystemExit(main())
