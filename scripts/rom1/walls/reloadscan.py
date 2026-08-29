"""rom1.walls.reloadscan - the sieve for the three DECLINED memory optimizations.

cl 5.0 hoists a loop-invariant load, keeps a common subexpression in a
register, and strength-reduces an induction variable, unless something in the
source forbids it.  So retail RE-READING a member where we read it once names
the precondition that failed, and the precondition is a source shape.  Three
kinds share one machine here, because all three are "how often does this side
touch that displacement, relative to the calls and the loops around it":

  ACROSS-A-CALL   retail loads `[r+D]` again after a call we hoist the load
                  above.  cl cannot keep a memory value in a register across
                  a call it does not own, so the reload means retail's SOURCE
                  re-reads the member after the call, and ours cached it in a
                  local.  The inverse - WE reload where retail does not - is
                  the same fact mirrored: retail's source holds a local.

  INSIDE-A-LOOP   retail loads `[r+D]` every iteration where we load it once
                  before the loop.  Hoisting is declined when the address may
                  alias a store in the body (a store through a pointer
                  PARAMETER is enough; the value being read from a GLOBAL is
                  what killed the "era anomaly" story) or when the object's
                  address escaped into a by-reference call.

  INDEX-VS-WALK   the loop body addresses its array as `[base+i*N+D]` on one
                  side and walks a pointer (`add r,N`) on the other.  cl
                  declines strength reduction when the induction variable is
                  still LIVE after the loop, so retail keeping the index is
                  evidence the source uses `i` again below the loop.

WHY DISPLACEMENT KEYS AND EXCLUSIVITY.  A base register is not comparable
across sides (allocation rotates it) but a member displacement is - it is the
class model.  The raw count delta is far too noisy to act on: 76 rows differ
on the call channel and 54 on the loop channel, and a delta of one is
scheduling.  What survives is the EXCLUSIVE delta - a displacement one side
reloads at least twice and the other never.  Over the 671-row sub-100 set that
is 2 rows on the call channel, 1 on the loop channel and 8 on the index
channel.  The loop channel additionally requires both sides to hold the SAME
NUMBER of loops, because a loop that exists on one side only (loopscan's own
class) makes every load inside it read as exclusive here.

THE BASE-FOLD FALSE POSITIVE, AND THE CONTROL FOR IT.  A displacement is only
comparable while both sides fold the same base into it.  When cl parks
`base + 0x10` in the register instead of `base`, EVERY key on that side shifts
by 0x10 at once and the channel reads a whole set of exclusives.  Measured:
`CNetSession::Verify` 0x0c0290 reports six, and it is a body already PROVEN at
100.00 - ours reads `[esi-0x14]/[esi-0x10]/[esi-0xc]` where retail reads
`[esi-0x4]/[esi+0x4]/[esi+0x10]`, the same three fields.  That is exactly the
failure mode a byte-identical control set cannot express, so the sieve tests
for it directly: it searches for the constant delta that best aligns the two
sides' whole read multiset, and a row whose best delta is non-zero is tagged
`base-fold` and left out of the hit list.  One row of six.

WHAT THE SIEVE STRUCTURALLY CANNOT SEE.  A displacement is not an object:
two different classes with a field at +0x8 share one key, and a reload of one
cancels against a hoist of the other.  The base-fold guard only catches a
UNIFORM shift - a single member reached through a `lea`d array base while the
rest of the function uses the object base still reads as two keys.  It reads
loads only, so a re-STORE is invisible.  And it names the displacement, never
the statement - the detail view prints the neighbourhood so a reader can find
it.

THE THREE CHANNELS ARE NOT EQUALLY PROVEN.  The index channel has a live
POSITIVE read by hand.  The call channel's positive was `CGrunt::PathScan`,
which this sieve found and the RECT-cursor fix CLOSED, so it survives as a
NEGATIVE control - it must stay silent - and its mechanics live in the
synthetic controls.  The loop channel has neither: its one surviving row
co-fires with the index channel and is a second view of that same difference,
so a loop-channel-only hit is a lead until someone reads it.

    rom1 walls reloadscan [--todo] [--unit U] [--limit N] [--json]
                            [--call | --loop | --iv]     one channel only
    rom1 walls reloadscan <rva|name> ...   one row, all three channels
    rom1 walls reloadscan --control        re-prove the verdict on every row read
                                             by hand (positives fire, closed rows
                                             stay silent)
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from collections import Counter, defaultdict

from rom1.walls import check_unit
from rom1.walls.escapescan import code_pair, frame_regs

#: `[reg+N]` / `[reg+idx*s+N]`; ESP is deliberately absent - a stack slot is a
#: frame-layout accident, a member displacement is the class model.
MEM = re.compile(r"\[(e[a-d]x|e[sd]i|ebx|ecx|ebp)(\+e[a-z]{2}\*\d)?"
                 r"([+-]0x[0-9a-f]+)?\]")
STORE_SIDE = re.compile(r"^(?:DWORD|BYTE|WORD|QWORD) PTR")
BRANCH = re.compile(r"^(j[a-z]+|loop[a-z]*)\s")
TARGET = re.compile(r"^[a-z]+\s+(0x[0-9a-f]+)$")
SCALED = re.compile(r"\[e[a-z]{2}\+e[a-z]{2}\*([248])")
STRIDE = re.compile(r"^add\s+e[a-z]{2},(0x[0-9a-f]+)$")

#: an `add r,K` that walks an array cursor rather than doing arithmetic
STRIDES = {2, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 48, 64}

#: instructions with no memory READ: `lea` computes an address, a push/branch
#: operand is not a load, and a `call`'s operand is a target.
NO_READ = ("lea", "call", "push", "nop", "j")


def loop_spans(lines, self_name: str = "") -> list[tuple[int, int]]:
    """(head index, branch index) for every backward branch that closes a
    body.  A branch carrying a relocation leaves the function."""
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
        if tgt < ln.addr and tgt in at:
            out.append((at[tgt], i))
    return out


def reads(lines) -> list[tuple[int, str]]:
    """(index, displacement) for every memory READ.

    Two operand shapes are dropped, both because their displacement is not a
    member key:

      * `[ebp+N]` when the body really builds an EBP frame.  With /O2 the
        frame pointer is omitted in 669 of 671 retail bodies, so EBP is a
        value register and its displacement IS a member - but in the two that
        do build a frame it is a local or an argument, and a frame offset is
        not comparable across sides.  `WarpTextureBlit` reported five bogus
        exclusives that way, all `[ebp-0x18]`..`[ebp-0x28]` stack slots.
      * `[base+idx*S+D]`, an ARRAY ELEMENT.  Its D is a base offset the two
        sides fold differently the moment their addressing shape differs -
        `ClaimTilesAround` reads `[ecx+eax*1-0x4]` where retail reads
        `[base+idx*4]`, the same field under keys `-0x4` and `+0x0`, and
        reported six exclusives that are one strength-reduction difference.
        That difference is real, and it is what the `iv` channel is for.
    """
    frame = set(frame_regs(lines))
    out = []
    for i, ln in enumerate(lines):
        asm = ln.asm
        if not asm or asm.startswith(NO_READ):
            continue
        parts = asm.split(None, 1)
        if len(parts) < 2:
            continue
        op, rest = parts
        if op == "mov" and "," in rest and \
                STORE_SIDE.match(rest.split(",", 1)[0].strip()):
            continue                      # the memory operand is the DESTINATION
        for m in MEM.finditer(rest):
            if m.group(1) in frame or m.group(2):
                continue
            out.append((i, m.group(3) or "+0x0"))
    return out


def channels(lines, self_name: str = "") -> tuple[Counter, Counter, Counter]:
    """(reloads across a call, loads inside a loop, loop-body shape)."""
    calls = sorted(i for i, ln in enumerate(lines) if ln.asm.startswith("call"))
    spans = loop_spans(lines, self_name)
    inside = set()
    for head, branch in spans:
        inside.update(range(head, branch + 1))

    across: Counter = Counter()
    in_loop: Counter = Counter()
    seen: dict[str, int] = {}
    for i, disp in reads(lines):
        prev = seen.get(disp)
        if prev is not None and bisect.bisect_left(calls, prev + 1) < \
                bisect.bisect_right(calls, i - 1):
            across[disp] += 1
        seen[disp] = i
        if i in inside:
            in_loop[disp] += 1

    shape: Counter = Counter()
    shape["loops"] = len(spans)
    for i, ln in enumerate(lines):
        if i not in inside:
            continue
        shape["scaled"] += len(SCALED.findall(ln.asm))
        m = STRIDE.match(ln.asm)
        if m and int(m.group(1), 16) in STRIDES:
            shape["stride"] += 1
    return across, in_loop, shape


def _key(value: int) -> str:
    return ("+" if value >= 0 else "-") + hex(abs(value))


def base_fold(base: Counter, target: Counter) -> int:
    """The constant that best aligns the two sides' whole read multiset.

    Non-zero means one side reached these members through a base register cl
    folded a fixed distance away, so EVERY displacement key shifted at once
    and the exclusives below are that shift, not a source difference.
    """
    def overlap(delta: int) -> int:
        return sum(min(n, target.get(_key(int(k, 16) + delta), 0))
                   for k, n in base.items())

    keys_b, keys_t = list(base)[:40], list(target)[:40]
    cands = {0} | {int(t, 16) - int(b, 16) for b in keys_b for t in keys_t}
    # ties go to the smallest shift, and to 0 above all
    best = max(cands, key=lambda d: (overlap(d), -abs(d)))
    return best if overlap(best) > overlap(0) else 0


def exclusive(base: Counter, target: Counter, floor: int = 2) -> dict:
    """A displacement one side touches at least `floor` times and the other
    never.  A shared key whose count merely differs is scheduling."""
    return {k: (base[k], target[k]) for k in set(base) | set(target)
            if base[k] != target[k] and 0 in (base[k], target[k])
            and max(base[k], target[k]) >= floor}


def scan_one(token: str, floor: int = 2) -> dict:
    binding, base, target = code_pair(token)
    ab, lb, sb = channels(base, binding.name)
    at, lt, st = channels(target, binding.name)
    call = exclusive(ab, at, floor)
    loop = exclusive(lb, lt, floor) if sb["loops"] == st["loops"] else {}
    iv = {}
    if sb["loops"] == st["loops"] and sb["loops"]:
        for k in ("scaled", "stride"):
            if abs(sb[k] - st[k]) >= floor:
                iv[k] = (sb[k], st[k])
    fold = 0
    if call or loop:
        fold = base_fold(Counter(d for _i, d in reads(base)),
                         Counter(d for _i, d in reads(target)))
        if fold:
            call, loop = {}, {}
    return {"call": {k: list(v) for k, v in call.items()},
            "loop": {k: list(v) for k, v in loop.items()},
            "iv": {k: list(v) for k, v in iv.items()},
            "loops": [sb["loops"], st["loops"]], "fold": fold,
            "n": len(call) + len(loop) + len(iv)}


def scan(rows: list[dict], floor: int = 2, progress=None) -> list[dict]:
    out = []
    for n, row in enumerate(rows, 1):
        rec = {k: row[k] for k in ("rva", "unit", "symbol", "cur", "hist_max")}
        try:
            rec.update(scan_one(row["rva"], floor))
        except BaseException as err:
            rec["error"] = str(err)[:110]
        out.append(rec)
        if progress and n % 100 == 0:
            print(f"  ... {n}/{len(rows)}", file=progress)
    return out


CHANNELS = {"call": "reload ACROSS a call",
            "loop": "load INSIDE a loop",
            "iv": "loop-body INDEX vs pointer walk"}


def report(rows: list[dict], limit: int, want: list[str]) -> None:
    ok = [r for r in rows if "n" in r]
    print(f"paired rows read: {len(ok)}   (errors {len(rows) - len(ok)})")
    for chan, label in CHANNELS.items():
        if chan in want:
            print(f"  exclusive {label:<32}: "
                  f"{sum(1 for r in ok if r[chan]):4d}")
    print(f"  suppressed, one side folds its base : "
          f"{sum(1 for r in ok if r.get('fold')):4d}")
    print()
    hit = [r for r in ok if any(r[c] for c in want)]
    for r in sorted(hit, key=lambda x: x["cur"])[:limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f} hist {r['hist_max']:6.2f}  loops "
              f"{r['loops'][0]}/{r['loops'][1]}  {r['unit']}/{r['symbol'][:44]}")
        for chan in want:
            for key, val in sorted(r[chan].items()):
                print(f"{'':>12}{CHANNELS[chan]:<32} {key:<8} "
                      f"ours {val[0]}  retail {val[1]}")


def detail(token: str) -> None:
    binding, base, target = code_pair(token)
    ab, lb, sb = channels(base, binding.name)
    at, lt, st = channels(target, binding.name)
    print(f"== {binding.unit}/{binding.name}")
    print(f"   loops: ours {sb['loops']}, retail {st['loops']}"
          + ("   (unequal - loopscan owns this row first)"
             if sb["loops"] != st["loops"] else ""))
    fold = base_fold(Counter(d for _i, d in reads(base)),
                     Counter(d for _i, d in reads(target)))
    if fold:
        print(f"   BASE-FOLD {fold:+#x}: one side reaches these members through "
              f"a base register folded {fold:+#x} away, so every displacement "
              f"below shifted at once - the exclusives are not source")
    for label, cb, ct in (("reload across a call", ab, at),
                          ("load inside a loop", lb, lt)):
        print(f"   -- {label}")
        for key in sorted(set(cb) | set(ct)):
            if cb[key] == ct[key]:
                continue
            flag = "  <-- EXCLUSIVE" if 0 in (cb[key], ct[key]) else ""
            print(f"      {key:<10} ours {cb[key]:3d}  retail {ct[key]:3d}{flag}")
    print(f"   -- loop-body shape   scaled index ours {sb['scaled']} retail "
          f"{st['scaled']}   stride add ours {sb['stride']} retail "
          f"{st['stride']}")
    keys = {k for k in set(ab) | set(at) | set(lb) | set(lt)
            if 0 in (ab[k], at[k]) or 0 in (lb[k], lt[k])}
    for label, lines in (("ours  ", base), ("retail", target)):
        rows = [f"{ln.addr:4x} {ln.asm}" for ln in lines
                if any(f"{k}]" in ln.asm for k in keys)]
        if rows:
            print(f"   -- {label} sites")
            for row in rows[:24]:
                print(f"      {row}")


#: hand-verified positives, re-derived from the disassembly in the session
#: that built this sieve.
CONTROL = {
    "0x0002d800": (True,
                   "iv channel POSITIVE: CBattlezMapConfig::ClaimTilesAround - "
                   "retail addresses the neighbour cells with a scaled index 21 "
                   "times (`[base+idx*4]`); we compute a byte offset and read "
                   "`[ecx+eax*1-0x4]`, scaling only twice"),
    "0x00057db0": (False,
                   "call channel NEGATIVE: CGrunt::PathScan was this sieve's "
                   "first positive - 15 loads of grid->m_bounds against retail's "
                   "3, four reloads across calls on each of +0x64/+0x68/+0x6c - "
                   "and the RECT-cursor fix closed it (89.19 -> 90.58).  It must "
                   "stay silent: a hit here is either the source regressing or "
                   "the detector inventing a reload"),
}
#: THE LOOP CHANNEL HAS NO VERIFIED ROW OF ITS OWN.  Its one surviving row,
#: `CDDSurface::ShadeBlt`, co-fires with the `iv` channel (`stride` 6 against 0)
#: and its `-0x2` reads are `p[-1]` on our pointer walk against retail's
#: subscript - the same difference, seen twice.  The synthetic controls in
#: `rom1 verify selftest -k DeclinedMemory` cover its mechanics; until a real
#: row fires it ALONE and is read by hand, treat a loop-only hit as a lead.


def control() -> int:
    bad = 0
    for rva, (expect, why) in CONTROL.items():
        try:
            rec = scan_one(rva)
        except BaseException as err:
            print(f"FAIL {rva}: {err}")
            bad += 1
            continue
        fires = bool(rec["n"])
        ok = fires == expect
        print(f"{'FIRES ' if fires else 'SILENT'} {rva}  "
              f"{'ok' if ok else 'UNEXPECTED'}  call={rec['call']} "
              f"loop={rec['loop']} iv={rec['iv']}")
        print(f"      {why}")
        bad += 0 if ok else 1
    if bad:
        print("\na control changed verdict: the row was fixed or regressed, or "
              "the detector did - read it, then re-pick")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls reloadscan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("rows", nargs="*", metavar="rva")
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--floor", type=int, default=2,
                    help="the exclusive side must reach this many touches")
    for chan, label in CHANNELS.items():
        ap.add_argument(f"--{chan}", action="store_true", help=label)
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.control:
        return control()
    if args.rows:
        for token in args.rows:
            detail(token)
        return 0
    want = [c for c in CHANNELS if getattr(args, c)] or list(CHANNELS)
    from rom1.walls.inventory import build
    rows = build(check_unit(args.unit), args.below, args.todo)
    scanned = scan(rows, args.floor, progress=None if args.json else sys.stderr)
    if args.json:
        json.dump(scanned, sys.stdout)
        return 0
    report(scanned, args.limit, want)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
