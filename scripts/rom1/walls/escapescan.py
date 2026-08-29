"""rom1.walls.escapescan - the ADDRESS-ESCAPE sieve (declined enregistration).

cl 5.0 performs an optimization unless something in the source forbids it, so
retail DECLINING one names the precondition that failed - and that precondition
is a source shape.  Enregistration is declined when a local's ADDRESS ESCAPES:
once `&x` is handed to a call the value must live in the frame, because the
callee may read or write it.  So retail materializing a frame address into a
call that we feed with a register (or do not make at all) says our source is
missing an `&` - a by-reference out-parameter, or a whole local OBJECT we never
declared.  It is the same family as the LICM find that moved `DrawGlyphRun`
70.89 -> 78.04 on one escaped identifier.

WHAT IS COMPARED, AND WHY IT IS KEYED ON THE CALLEE.  The obvious statistic -
"how many `lea r,[esp+N]` does each side emit" - is NOT a source fact: cl
rematerializes a frame address once per use region, so the count moves with
register pressure.  What IS a source fact is which CALL receives a frame
address, and the callee's relocation target is the one key that means the same
thing on both sides.  So the census is, per callee referent:

    &arg    that call site is passed the address of a local
    &this   that call site's RECEIVER is a local object

and the EXCLUSIVE deltas (one side never feeds that callee an address) are the
signal.  A count that merely differs - `~CString` 12 vs 3 - is cross-jump merge
degree, the same caveat `aggregate-copies` carries.

FOUR MEASURED DETECTOR BUGS, each of which inflated the census and is now a
control in the selftest.  This class of tool fails silently, so they are named:

  * `[ebp+N]` IS NOT A FRAME SLOT HERE.  With /O2 cl omits the frame pointer -
    669 of 671 sub-100 retail bodies have no `push ebp / mov ebp,esp` - so EBP
    is an ordinary value register and `lea eax,[ebp+0x4]` is usually a field of
    a heap object.  Treating it as a frame address reported 15 rows where the
    honest count is 3.  EBP counts only when the prologue really builds a frame.
  * A `push` CROSSED BY A BRANCH belongs to a cross-jumped block, not to the
    next call in linear order.  Retail's shared-return idiom (`lea edx,[esp+N] /
    push edx / jmp <shared>`) was being attributed to whatever call happened to
    follow.
  * ECX is only a RECEIVER at a __thiscall callee.  At `_fopen`, `__imp__PtInRect@12`
    or `?Format@CString@@QAAXPBDZZ` (the `A` is __cdecl) a live frame address in
    ECX is a leftover, not an argument.
  * A CONSTRUCTOR returns `this` in EAX, so reusing EAX versus re-`lea`ing the
    same slot is a cl choice with no source content.  The rule applies to `??0`
    only: it was first written for every call and promptly mislabelled
    `CString::GetBuffer`'s heap pointer as a frame address.

WHAT THE SIEVE STRUCTURALLY CANNOT SEE.  An escape that never reaches a call -
an address stored into a struct, an array indexed only locally, a local whose
address feeds an intrinsic cl expanded inline - is invisible.  So is an escape
BOTH sides make, even if they escape different variables; and so is any
difference in WHICH local escaped, since a frame offset is not comparable
across sides.  It names the call, never the variable.

    rom1 walls escapescan [--todo] [--unit U] [--limit N] [--all] [--json]
    rom1 walls escapescan <rva|name> ...   one row, both channels in full
    rom1 walls escapescan --control        re-prove the verdict on every row read
                                             by hand (positives fire, closed rows
                                             stay silent)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

from rom1.delink.coffx import Obj
from rom1.walls import check_unit
from rom1.walls.diagnose import _find_function, _jump_table_bytes, _locate
from rom1.walls.semdiff import NORM, _decode

MOV_RR = re.compile(r"^mov\s+(e[a-z]{2}),(e[a-z]{2})$")
DEFINES = re.compile(r"^(?:mov|lea|add|sub|xor|or|and|inc|dec|pop|movzx|movsx"
                     r"|imul|shl|shr|sar|neg|not|cdq)\s+(e[a-z]{2})\b")
PUSH_R = re.compile(r"^push\s+(e[a-z]{2})$")
CONTROL_FLOW = re.compile(r"^(j[a-z]+|loop[a-z]*|ret)\b")

#: `?f@C@@QAE...`, `??1C@@UAE@XZ`: the third letter after `@@` is the calling
#: convention and `E` is __thiscall.  `QAA` is __cdecl, `_name` is C, and
#: `__imp__f@12` is a stdcall import - ECX carries nothing at any of those.
THISCALL = re.compile(r"@@[A-Z]{2}E")


def code_pair(token: str):
    """(binding, base code lines, target code lines) with each side's own
    switch/index table removed.

    `semdiff.pair_lines` keeps the table: it filters by a line's relocation
    referent, and a table entry decoding as a 2-byte junk instruction can miss
    the relocation inside it.  Three of this sieve's first seven signedness
    hits were table bytes decoding as `cdq` and `mul`, so the byte-range filter
    `diagnose` uses is applied here instead.
    """
    binding, why = _locate(token)
    if binding is None:
        raise SystemExit(f"[escapescan] {why}")
    target_path = NORM / "target" / f"{binding.unit}.c.obj"
    if not target_path.exists():
        target_path = NORM / "target" / f"{binding.unit}.obj"
    out = []
    for path in (NORM / "base" / f"{binding.unit}.obj", target_path):
        body, rel, _size = _find_function(Obj(path), binding.name)
        if body is None:
            raise SystemExit(f"[escapescan] {path.name} does not define "
                             f"{binding.name}")
        table = _jump_table_bytes(rel, binding.name)
        out.append([ln for ln in _decode(body, rel) if ln.addr not in table])
    return binding, out[0], out[1]


def frame_regs(lines) -> tuple[str, ...]:
    """The registers that really address this body's frame."""
    head = [ln.asm for ln in lines[:4]]
    if len(head) >= 2 and head[0] == "push ebp" and head[1] == "mov ebp,esp":
        return ("esp", "ebp")
    return ("esp",)


def escapes(lines) -> tuple[Counter, Counter]:
    """({callee: sites passed a frame ADDRESS}, {callee: sites whose RECEIVER
    is a frame address})."""
    lea = re.compile(r"^lea\s+(e[a-z]{2}),\[(?:%s)(?:[+-]0x[0-9a-f]+)?"
                     r"(?:\+e[a-z]{2}\*\d)?\]$" % "|".join(frame_regs(lines)))
    held: set[str] = set()          # registers currently holding a frame address
    pending = 0                     # frame addresses pushed for the next call
    arg: Counter = Counter()
    this: Counter = Counter()
    for ln in lines:
        asm = ln.asm
        m = lea.match(asm)
        if m:
            held.add(m.group(1))
            continue
        mv = MOV_RR.match(asm)
        if mv:
            (held.add if mv.group(2) in held else held.discard)(mv.group(1))
            continue
        pu = PUSH_R.match(asm)
        if pu:
            pending += pu.group(1) in held
            continue
        if asm.startswith("call"):
            key = ln.ref or "<indirect>"
            if pending:
                arg[key] += 1
            receiver = "ecx" in held
            if receiver and THISCALL.search(key):
                this[key] += 1
            held -= {"eax", "ecx", "edx"}
            if receiver and key.startswith("??0"):
                held.add("eax")     # a ctor hands `this` back in EAX
            pending = 0
            continue
        if CONTROL_FLOW.match(asm):
            pending = 0             # a pushed address the branch carries away
            continue
        d = DEFINES.match(asm)
        if d:
            held.discard(d.group(1))
    return arg, this


def exclusive(base: Counter, target: Counter) -> dict:
    """The callees ONE side never feeds an address.  A shared callee whose
    count merely differs is cross-jump merge degree, not source."""
    return {k: (base[k], target[k]) for k in set(base) | set(target)
            if base[k] != target[k] and 0 in (base[k], target[k])}


def scan_one(token: str) -> dict:
    _binding, base, target = code_pair(token)
    ab, tb = escapes(base)
    at, tt = escapes(target)
    da, dt = exclusive(ab, at), exclusive(tb, tt)
    missing = sum(v[1] - v[0] for v in list(da.values()) + list(dt.values())
                  if v[1] > v[0])
    return {"arg": {k: list(v) for k, v in da.items()},
            "this": {k: list(v) for k, v in dt.items()},
            "n": len(da) + len(dt), "missing": missing}


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
    ok = [r for r in rows if "n" in r]
    hit = [r for r in ok if r["n"]]
    ours = sum(1 for r in hit if not r["missing"])
    print(f"paired rows read: {len(ok)}   (errors {len(rows) - len(ok)})")
    print(f"  a callee ONE side never &-feeds : {len(hit):4d}   "
          f"(retail escapes and we do not: {len(hit) - ours})")
    print(f"  clean                           : {len(ok) - len(hit):4d}")
    print()
    for r in sorted(hit if not show_all else ok, key=lambda x: x["cur"])[:limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f}  {r['unit']}/{r['symbol'][:50]}")
        for chan, tag in (("arg", "&arg "), ("this", "&this")):
            for key, val in sorted(r.get(chan, {}).items()):
                print(f"{'':>12}{tag} -> {key[:50]:<50} "
                      f"ours {val[0]}  retail {val[1]}")


def detail(token: str) -> None:
    binding, base, target = code_pair(token)
    ab, tb = escapes(base)
    at, tt = escapes(target)
    print(f"== {binding.unit}/{binding.name}")
    print(f"   frame register(s): ours {'/'.join(frame_regs(base))}, "
          f"retail {'/'.join(frame_regs(target))}")
    for tag, cb, ct in (("&arg ", ab, at), ("&this", tb, tt)):
        for key in sorted(set(cb) | set(ct)):
            flag = "  <-- EXCLUSIVE" if 0 in (cb[key], ct[key]) \
                and cb[key] != ct[key] else ""
            if cb[key] != ct[key] or flag:
                print(f"   {tag} {key[:56]:<56} ours {cb[key]}  "
                      f"retail {ct[key]}{flag}")


#: hand-verified positives, re-derived from the disassembly in the session
#: that built this sieve.
CONTROL = {
    "0x0009cf00": (True,
                  "POSITIVE: CLightFx::CLightFx - retail expands CLogicRecordRegistry::Find "
                  "at the FIRST of its three sites, so the inlined "
                  "`CObject* found = NULL` is materialized and its address goes "
                  "to CMapStringToOb::Lookup; we call the out-of-line Find at "
                  "all three (the adjudicated DDrawWorkerCacheFindInline case)"),
    "0x0017a460": (True,
                  "POSITIVE: FontRenderer::DrawWrapped - retail calls CRect::Width() "
                  "out of line on a stack CRect five times; we expand it"),
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
        fires = bool(rec["n"])
        ok = fires == expect
        print(f"{'FIRES ' if fires else 'SILENT'} {rva}  "
              f"{'ok' if ok else 'UNEXPECTED'}  arg={rec['arg']} this={rec['this']}")
        print(f"      {why}")
        bad += 0 if ok else 1
    if bad:
        print("\na control changed verdict: the row was fixed or regressed, or "
              "the detector did - read it, then re-pick")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls escapescan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("rows", nargs="*", metavar="rva")
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--control", action="store_true")
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
