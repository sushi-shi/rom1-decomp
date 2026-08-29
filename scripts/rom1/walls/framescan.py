"""rom1.walls.framescan - the frame-size sieve over the whole worklist.

cl 5.0 assigns stack slots by SCOPE, not by live range, so a temp written at
function scope but used by ONE branch keeps its own dword where retail (which
declared it inside the branch) overlays it with the other branches' temps.
Our frame is then a slot larger, every `[esp+N]` in the body shifts, and a
byte-identical reconstruction reads as a several-hundred-line diff. That is
the shape docs/patterns/switch-arm-locals-overlay-only-when-scoped.md names.

This sieve finds those rows mechanically. For every paired sub-100 function it
reads the SAME evidence objdiff scored (the normalized pair under
build/objdiff/compare-new) and reports two numbers:

    frame delta   base `sub esp,N` (plus a `__chkstk` reservation) minus
                  target's. POSITIVE = we carry slots retail does not.
    residual      diff lines left after masking BOTH the `[esp+N]`
                  displacements and the intra-function branch targets. This
                  is the sharp part: a pure frame-inflation hit reads ~0,
                  because everything the frame delta perturbs is masked out.

Ranked by residual, the top of the list is the hit list; the tail is a frame
delta riding on top of an unrelated reconstruction difference.

THE INVERSE SIGN IS THE PRODUCTIVE ONE, AND `--folded` RANKS IT. A NEGATIVE
delta means retail has a slot we folded away - a variable we merged into an
expression, an aggregate we scalarised, or a by-value temp we named. That
direction closed three rows on 2026-08-23 and the default ranking hides every
one of them, because ranking by RESIDUAL puts frame-equal rows near 100% at the
head and the whole `residual<=4` hit list is empty in both signed buckets:

    CTriggerMgr::ToggleToolTargeting   0x7d450  0 vs 0x8  85.71 -> 100.00 EXACT
    CStatusBarMgr::UpdateFalling 0x107590 0 vs 0x10 89.65 ->  97.91
    PolyIsConvexCW               0x145e30 0xc vs 0x10 85.70 -> 93.23

Each was the SAME question - which source entity owns the bytes retail reserved
and we did not - with three different answers: an unnamed by-value accessor
temp, a RECT whose field-assignment order decides whether cl keeps the local,
and six named coordinates that push the deltas past cl's x87 stack budget.

    rom1 walls framescan [--todo] [--unit U] [--limit N] [--all] [--folded] [--json]

Cost: one objdump decode per side per row (~4 min for the full ~580-row todo
queue), so it is a sweep tool, not an inner-loop one. `walls diagnose` and
`walls semdiff` adjudicate the individual rows it flags.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher

from rom1.walls import check_unit
from rom1.walls.semdiff import pair_lines

#: the frame reservation itself, and cl's big-frame `mov eax,N; call __chkstk`
SUB_ESP = re.compile(r"^sub\s+esp,(0x[0-9a-f]+|\d+)$")
MOV_EAX = re.compile(r"^mov\s+eax,(0x[0-9a-f]+)$")
PUSH_SAVED = re.compile(r"^push\s+(ebp|esi|edi|ebx)$")

ESP_DISP = re.compile(r"\[esp([+-]0x[0-9a-f]+)?\]")
LOCAL_BRANCH = re.compile(r"^(j\w+|call|loop)\s+0x[0-9a-f]+$")
FRAME_IMM = re.compile(r"^(sub|add)\s+esp,")

#: the prologue ends at the first transfer of control, `__chkstk` excepted.
#: A fixed instruction window does not: it counted ARGUMENT pushes as
#: callee-saves on 108 base / 107 target rows of the 595-row todo queue,
#: asymmetrically on 9, and left an unconsumed `mov eax,N` able to be charged
#: to a later `__chkstk` on 38/40 more. Neither is visible on an exact row -
#: both sides mis-parse identically there, so the delta is 0 either way.
TRANSFER = re.compile(r"^(?:call|j\w+|loop\w*|ret|leave|int3?)\b")


def frame(lines) -> tuple[int, int]:
    """(reserved bytes, saved-register pushes) read from the prologue.

    cl 5.0 saves ebx/ebp/esi/edi and each only once, so a SECOND push of one is
    already an argument and ends the run; so does any transfer of control. The
    `mov eax,N; call __chkstk` big-frame form is the one call that does not,
    and its immediate must be the one directly before the call - an unrelated
    `mov eax,N` earlier in the prologue is not a frame size.
    """
    reserved = saved = 0
    seen: set[str] = set()
    pending = None
    for ln in lines:
        asm = ln.asm
        m = SUB_ESP.match(asm)
        if m:
            reserved += int(m.group(1), 0)
            pending = None
            continue
        m = MOV_EAX.match(asm)
        if m:
            pending = int(m.group(1), 16)
            continue
        if TRANSFER.match(asm):
            if asm.startswith("call") and ln.ref and "chkstk" in ln.ref:
                reserved += pending or 0
                pending = None
                continue
            break
        m = PUSH_SAVED.match(asm)
        if m:
            if m.group(1) in seen:
                break
            seen.add(m.group(1))
            saved += 1
        pending = None
    return reserved, saved


def masked(lines, self_name: str) -> list[str]:
    """The instruction stream with everything a frame shift perturbs removed:
    esp displacements, intra-function branch targets, and the frame immediate."""
    out = []
    for ln in lines:
        asm = ESP_DISP.sub("[esp+?]", ln.asm)
        if LOCAL_BRANCH.match(asm) and ln.ref in (None, self_name):
            asm = asm.split()[0] + " L"
        if FRAME_IMM.match(asm):
            asm = "FRAME"
        out.append(asm + (f"|{ln.ref}" if ln.ref else ""))
    return out


def scan_one(rva: str) -> dict:
    binding, base, target = pair_lines(rva)
    base_res, base_push = frame(base)
    tgt_res, tgt_push = frame(target)
    ops = SequenceMatcher(None, masked(base, binding.name),
                          masked(target, binding.name),
                          autojunk=False).get_opcodes()
    residual = sum(max(i2 - i1, j2 - j1)
                   for op, i1, i2, j1, j2 in ops if op != "equal")
    return {"base_frame": base_res, "tgt_frame": tgt_res,
            "base_push": base_push, "tgt_push": tgt_push,
            "base_insns": len(base), "tgt_insns": len(target),
            "residual": residual}


def scan(rows: list[dict], progress=None) -> list[dict]:
    out = []
    for n, row in enumerate(rows, 1):
        rec = {k: row[k] for k in ("rva", "unit", "symbol", "cur", "hist_max")}
        try:
            rec.update(scan_one(row["rva"]))
        except BaseException as err:          # SystemExit from the locator too
            rec["error"] = str(err)[:110]
        out.append(rec)
        if progress and n % 50 == 0:
            print(f"  ... {n}/{len(rows)}", file=progress)
    return out


def report(rows: list[dict], limit: int, show_all: bool,
           folded: bool = False) -> None:
    ok = [r for r in rows if "base_frame" in r]
    delta = lambda r: r["base_frame"] - r["tgt_frame"]           # noqa: E731
    larger = [r for r in ok if delta(r) > 0]
    smaller = [r for r in ok if delta(r) < 0]
    equal = [r for r in ok if delta(r) == 0]
    pure = [r for r in larger if r["residual"] <= 4]
    print(f"paired rows read: {len(ok)}   (errors {len(rows) - len(ok)})")
    print(f"  frame LARGER  than retail : {len(larger):4d}  "
          f"(residual<=4, the sieve's hit list: {len(pure)})")
    print(f"  frame SMALLER than retail : {len(smaller):4d}  "
          f"(residual<=4: {len([r for r in smaller if r['residual'] <= 4])})")
    print(f"  frame EQUAL               : {len(equal):4d}  "
          f"(residual<=4: {len([r for r in equal if r['residual'] <= 4])})")
    print()
    if folded:
        # retail reserved bytes we did not: rank by how many, then by how much
        # of the function is still open. Residual is NOT the key here - a
        # missing local perturbs every [esp+N] below it, so these rows are
        # large-residual by construction.
        shown = smaller
        key = lambda x: (delta(x), x["cur"])                     # noqa: E731
    else:
        shown = ok if show_all else larger + smaller
        key = lambda x: x["residual"]                            # noqa: E731
    print(f"{'rva':>10} {'cur':>7} {'base':>6} {'tgt':>6} {'d':>5} "
          f"{'resid':>6} {'push':>5}  unit/symbol")
    for r in sorted(shown, key=key)[:limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f} {r['base_frame']:6d} "
              f"{r['tgt_frame']:6d} {delta(r):5d} {r['residual']:6d} "
              f"{r['base_push']}/{r['tgt_push']:<3}  "
              f"{r['unit']}/{r['symbol'][:56]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls framescan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true",
                    help="the campaign queue rather than every sub-100 row")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--all", action="store_true",
                    help="list the equal-frame rows too")
    ap.add_argument("--folded", action="store_true",
                    help="only rows where RETAIL reserved more than we did, "
                         "ranked by that delta: a local we folded away")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    from rom1.walls.inventory import build
    rows = build(check_unit(args.unit), args.below, args.todo)
    scanned = scan(rows, progress=None if args.json else sys.stderr)
    if args.json:
        json.dump(scanned, sys.stdout)
        return 0
    report(scanned, args.limit, args.all, args.folded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
