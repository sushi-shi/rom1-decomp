"""rom1.walls.signscan - the ARITHMETIC signedness sieve.

`jccscan` owns comparison signedness: the branch mnemonic IS the source
operator, so `jl` against retail's `jb` is a signedness defect.  This is the
other half.  cl 5.0 lowers a division, a modulo, a shift and a narrow load
through COMPLETELY DIFFERENT instruction sequences depending on the declared
signedness of the operand, and objdiff never masks a mnemonic - so the two
sides disagreeing is not a schedule coin, it is a different TYPE in the
source.  Unlike every other wall class this one is a CORRECTNESS difference:
`(unsigned)x / 10` and `(int)x / 10` compute different answers.

MEASURED against cl 5.0 SP3 /O2 (the probe is reproduced in the selftest, and
the divisor arithmetic below is checked against it):

    construct          signed                          unsigned
    ---------------------------------------------------------------------
    / K (non-pow2)     mov eax,M / imul r / [add] /    mov eax,M / mul m /
                       sar eax,S / shr r,0x1f / add    mov eax,edx / shr eax,S
    / 2^n              cdq / and edx,2^n-1 /           shr eax,n
                       add eax,edx / sar eax,n
    % 2^n              cdq / xor / sub / and 2^n-1 /   and eax,2^n-1
                       xor / sub
    % K (non-pow2)     cdq / idiv r / mov eax,edx      xor edx,edx / div r /
                                                       mov eax,edx
    / variable         cdq / idiv m                    xor edx,edx / div m
    >> n               sar                             shr
    narrow load        movsx                           movzx

The MAGIC CONSTANT alone does NOT name the signedness - `/9` and `/30` use
the same 0x38e38e39 / 0x88888889 on both sides.  What names it is the
one-operand `imul` versus `mul`, the `idiv` versus `div`, and the `cdq`
versus `xor edx,edx`.  The divisor itself IS recoverable, from the magic and
the shift together:  d = round(2**(32+S) / M)  with M read UNSIGNED.

WHAT IS COUNTED, AND WHY IT IS COUNTED RATHER THAN MATCHED.  A first draft
matched the idiom as a fixed instruction SEQUENCE and reported six rows; four
were artifacts.  Two came from cl interleaving an unrelated instruction into
the middle of the sequence (`cdq / xor eax,edx / mov ecx,[ebx+0x18] / sub
eax,edx / and eax,0x3`), and one from the mask living in a register rather
than an immediate (`and eax,ebx` where EBX holds 1).  Both are schedule and
allocation, not source.  So the sieve counts POSITION-INDEPENDENT anchor
tokens instead; sequence reconstruction survives only in the per-row detail
view, which says so.  A further three came from the function's own switch
jump table decoding as `cdq`/`mul`; that data is removed here the way
`diagnose` removes it.

THE DECISIVE SET is deliberately narrower than the full delta:

  * a `cdq` / `idiv` / `div` / one-operand `imul` / `mul` COUNT delta - each
    of those five appears only in a signed-or-unsigned lowering;
  * a `sar` <-> `shr` swap at the SAME immediate in OPPOSITE directions - one
    side shifts a signed value where the other shifts an unsigned one;
  * a `movsx` <-> `movzx` swap at the same WIDTH, likewise.

`shr r,0x1f` is excluded from the shift census: it is the sign-extraction
step of the SIGNED magic sequence, so counting it inverts the reading.

WHAT THE SIEVE STRUCTURALLY CANNOT SEE.  A signedness difference that cl
lowers identically - `x / 2` where x is provably non-negative, `>> 0`, a mask
that makes `sar` and `shr` agree on every demanded bit - moves no byte and is
invisible here.  It cannot see the signedness of a value that never reaches
one of these seven lowerings.  And a count delta names the FUNCTION, never
the statement: two divisions of different divisors cancel in the census.

    rom1 walls signscan [--todo] [--unit U] [--limit N] [--all] [--json]
    rom1 walls signscan <rva|name> ...   one row, every anchor in context
    rom1 walls signscan --control        re-prove the verdict on every row
                                           read by hand: a POSITIVE that must
                                           still fire, and each row this sieve
                                           already CLOSED, which must stay
                                           silent
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

from rom1.walls import check_unit
from rom1.walls.escapescan import code_pair

#: the one-operand (64-bit product / 64-bit dividend) forms.  A two-operand
#: `imul eax,ecx` is ordinary multiplication and carries no signedness claim.
ONE_OP = re.compile(r"^(imul|mul|idiv|div)\s+[^,]+$")
SHIFT = re.compile(r"^(sar|shr)\s+\S+,(0x[0-9a-f]+|1)$")
EXTEND = re.compile(r"^(movsx|movzx)\s+\S+,(BYTE|WORD) PTR")
MAGIC = re.compile(r"^mov\s+e[a-z]{2},(0x[0-9a-f]{8})$")

#: the sign-extraction of the SIGNED magic sequence, not an unsigned shift
SIGN_BIT = "0x1f"

ANCHORS = ("cdq", "idiv", "div", "imul", "mul")


def divisor(magic: int, shift: int) -> int | None:
    """The constant divisor behind a magic multiply, or None.

    d = round(2**(32+S) / M), M read UNSIGNED.  cl's signed form for a
    divisor whose magic overflows into the sign bit adds the dividend back
    (`add eax,ecx` between the `imul` and the `sar`); reading M unsigned
    covers both spellings with one formula.
    """
    if magic <= 0:
        return None
    exact = (1 << (32 + shift)) / magic
    near = round(exact)
    return near if near >= 2 and abs(exact - near) < 0.02 else None


def features(lines) -> Counter:
    """The position-independent signedness anchors of one side."""
    c: Counter = Counter()
    for ln in lines:
        asm = ln.asm
        m = ONE_OP.match(asm)
        if m:
            c[m.group(1)] += 1
        if asm == "cdq":
            c["cdq"] += 1
        s = SHIFT.match(asm)
        if s and s.group(2) != SIGN_BIT:
            c[(s.group(1), s.group(2))] += 1
        e = EXTEND.match(asm)
        if e:
            c[(e.group(1), e.group(2))] += 1
    return c


def _swap(delta: dict, kinds: tuple[str, str]) -> dict:
    """The keys where one mnemonic rose and its opposite-signedness twin fell
    at the SAME operand - a swap, not two independent count changes."""
    out = {}
    for key, val in delta.items():
        if not isinstance(key, tuple) or key[0] not in kinds:
            continue
        twin = (kinds[1] if key[0] == kinds[0] else kinds[0], key[1])
        if twin in delta and (delta[key][0] - delta[key][1] > 0) != (
                delta[twin][0] - delta[twin][1] > 0):
            out[key] = val
    return out


def decisive(base: Counter, target: Counter) -> dict:
    """The subset of the delta whose presence NAMES a signedness."""
    delta = {k: (base[k], target[k]) for k in set(base) | set(target)
             if base[k] != target[k]}
    out = {k: v for k, v in delta.items()
           if isinstance(k, str) and k in ANCHORS}
    out.update(_swap(delta, ("sar", "shr")))
    out.update(_swap(delta, ("movsx", "movzx")))
    return out


def sites(lines) -> list[str]:
    """Per-row DETAIL: each anchor with its neighbourhood, and the recovered
    divisor where the magic and the shift are adjacent.  This part IS
    position-dependent - cl interleaves - so it explains, it never decides."""
    asms = [ln.asm for ln in lines]
    out = []
    for i, asm in enumerate(asms):
        m = ONE_OP.match(asm)
        if not (m or asm == "cdq"):
            continue
        note = ""
        if m and m.group(1) in ("imul", "mul"):
            magic = next((int(mm.group(1), 16)
                          for j in range(i - 1, max(-1, i - 6), -1)
                          for mm in [MAGIC.match(asms[j])] if mm), None)
            want = "sar" if m.group(1) == "imul" else "shr"
            shift = None
            for j in range(i + 1, min(len(asms), i + 7)):
                s = SHIFT.match(asms[j])
                if s and s.group(1) == want and s.group(2) != SIGN_BIT:
                    shift = 1 if s.group(2) == "1" else int(s.group(2), 16)
                    break
            if magic is not None:
                d = divisor(magic, shift or 0)
                sign = "signed" if m.group(1) == "imul" else "unsigned"
                note = (f"   <- {sign} / {d}" if d else
                        f"   <- {sign} magic {magic:#x} >> {shift}")
        out.append(" / ".join(asms[max(0, i - 2):i + 6]) + note)
    return out


def scan_one(token: str) -> dict:
    binding, base, target = code_pair(token)
    fb, ft = features(base), features(target)
    dec = decisive(fb, ft)
    return {"decisive": {str(k): v for k, v in dec.items()},
            "ndec": len(dec),
            "worst": max((abs(a - b) for a, b in dec.values()), default=0)}


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
    ok = [r for r in rows if "decisive" in r]
    hit = [r for r in ok if r["ndec"]]
    print(f"paired rows read: {len(ok)}   (errors {len(rows) - len(ok)})")
    print(f"  a sign-naming token differs : {len(hit):4d}")
    print(f"  clean                       : {len(ok) - len(hit):4d}")
    print()
    print(f"{'rva':>10} {'cur':>7} {'worst':>6}  unit/symbol")
    for r in sorted(hit if not show_all else ok,
                    key=lambda x: x["cur"])[:limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f} {r['worst']:6d}  "
              f"{r['unit']}/{r['symbol'][:52]}")
        for key, val in sorted(r["decisive"].items()):
            print(f"{'':>12}{key:<22} ours {val[0]}  retail {val[1]}")


def detail(token: str) -> None:
    binding, base, target = code_pair(token)
    fb, ft = features(base), features(target)
    print(f"== {binding.unit}/{binding.name}")
    dec = decisive(fb, ft)
    if not dec:
        print("   no sign-naming token differs")
    for key, val in sorted(dec.items(), key=str):
        print(f"   {str(key):<24} ours {val[0]}  retail {val[1]}")
    for label, lines in (("ours  ", base), ("retail", target)):
        print(f"   -- {label}")
        for s in sites(lines):
            print(f"      {s}")


#: hand-verified positives, each re-derived from the disassembly in the
#: session that built this sieve.  A sieve nobody has seen FIRE is a green
#: light, not a check.
CONTROL = {
    "0x00107d00": (True,
                   "POSITIVE: CStatusBarMgr::StartChipMachineCycle - the SAME "
                   "inlined LCG expands eight times against one `holdrand` "
                   "relocation; retail shifts the seed `shr` in the four "
                   "`range == 0` coin arms and `sar` in the four `% range` "
                   "arms, we emit `sar` at all eight"),
    "0x000810f0": (False,
                   "NEGATIVE: CRom1MapMgr::BuildCellAttributes held retail's two "
                   "extra `cdq` - a signed `/ 32` we had hand-expanded as "
                   "`(px + (px >> 31 & 0x1f)) >> 5` - and `px / TILE_SIZE_PX` "
                   "closed it.  It must stay silent"),
}


def control() -> int:
    bad = 0
    for rva, (expect, why) in CONTROL.items():
        try:
            rec = scan_one(rva)
        except BaseException as err:
            print(f"FAIL {rva}: {err}")
            bad += 1
            continue
        fires = bool(rec["ndec"])
        ok = fires == expect
        print(f"{'FIRES ' if fires else 'SILENT'} {rva}  "
              f"{'ok' if ok else 'UNEXPECTED'}  {rec['decisive']}")
        print(f"      {why}")
        bad += 0 if ok else 1
    if bad:
        print("\na control changed verdict: the row was fixed or regressed, or "
              "the detector did - read it, then re-pick")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls signscan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("rows", nargs="*", metavar="rva",
                    help="adjudicate these rows instead of sweeping")
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--control", action="store_true",
                    help="re-prove the detector fires on a known positive")
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


if __name__ == "__main__":
    raise SystemExit(main())
