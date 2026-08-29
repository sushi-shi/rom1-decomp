"""rom1.walls.thisscan - the dropped-receiver (`this`) sieve.

A `__thiscall` member and a free `__stdcall` with the SAME stack arguments
compile to the same callee bytes: the receiver travels in ECX, so it costs the
callee nothing. `CLatencyList::GetSelItemData` scored 100% EXACT while modelled
as a free `__stdcall`, and stayed exact after it became a member. The defect is
therefore invisible in the callee and invisible to every test `walls diagnose`
runs (call-set, CFG, frame): only a CALLER shows it, as an ECX load retail
emits and we do not.

    retail   mov ecx,DWORD PTR [ecx+0x60]   ; m_slotList - never read again
             call ?GetSelItemData@...
    ours     call ?GetSelItemData@...

cl 5.0 does not emit dead loads, so a load whose value nothing consumes before
the call IS a receiver. This sieve reads the normalized pair objdiff scored and
reports, per call site, the callees retail gives a receiver and we do not.

    rom1 walls thisscan [--todo] [--unit U] [--below P] [--above P]
                          [--inverse] [--all-callees] [--receivers] [--arity]
                          [--limit N] [--json]
    rom1 walls thisscan --retail [--probe RVA...]

`--retail` is the STRONGER form and needs no score at all - read it first.
The paired screen below is bounded by what the compare report can show; the
retail screen is bounded only by the retail image, and it found the row the
paired screen structurally could not (see RETAIL SCREEN, below).

The default screen requires ALL FOUR of:

  dead        nothing between the ECX definition and the call reads ECX. This
              is the discriminator, not a refinement: retail routinely
              materialises a pushed ARGUMENT through ECX (`mov ecx,[ebx];
              push eax; push ecx; call CellTargetable`) where we use EDX, and
              every such row is a register-name rotation, not a receiver.
  ours-lacks  no ECX definition reaches our call site. Our side is scanned
              with a WEAKER rule that walks back past branch boundaries to the
              previous `call` (which clobbers ECX anyway), because a receiver
              we materialise before a guard branch and retail re-materialises
              after it is not a missing receiver.
  counts      both sides call the callee the same number of times, and retail
              gives a receiver at EVERY one. A receiver at some sites only is
              a value that happens to live in ECX.
  free callee the callee is not already mangled `__thiscall`. A hit on a
              member is a wrong-OBJECT question (or, usually, this sieve
              failing to see our receiver), not a dropped-`this` one.

`--inverse` runs the mirror: WE pass a receiver retail does not, i.e. a free
function modelled as a member.

Two adjacent screens share the machinery, both for the same reason - the callee
cannot witness the defect:

  --receivers  BOTH sides pass a receiver, but from a different member or
               global: a wrong-OBJECT bug. The callee must be mangled
               `__thiscall`, because against a free callee ECX is an ordinary
               scratch register and the "receiver" is whichever step of a
               pointer chain landed there.
  --arity      the caller's `__cdecl` cleanup (`add esp,N`, which cl also
               spells `pop ecx`) against retail's. A `__cdecl` callee does not
               clean up, so a trailing argument it never reads is invisible in
               ITS bytes exactly as a receiver is - the caller is again the
               only witness. cl merges the cleanup of adjacent calls, so read
               the surrounding run before believing a row.

FALSE-POSITIVE TAXONOMY - each was observed on a flagged row whose model was
right, and each is what one of the four filters above removes:

  * argument through ECX     retail pushes the value it just loaded into ECX;
                             we load the same value into EDX/EAX. Killed by
                             `dead` (`?ActiveWait@@YAXI@Z` from RetireScene,
                             `?CellTargetable@@YAHHH@Z` from
                             StepGooSuckerBehavior, `?RotateRasterize@@...`
                             from ImageRotateBlit - all three consumed).
  * receiver before a guard  ours holds the receiver in ECX from before the
                             `je` that retail re-loads after. Killed by the
                             weaker our-side rule (`?Reset@CLightFxMgr@@QAEXXZ`
                             from CRom1Mgr::Close,
                             `?HitClick@CActionOptionsMenuBar@@QAEHHH@Z` from
                             CTriggerMgr::PlaceObjectFull).
  * `pop ecx`                cl 5.0 spells `add esp,4` as `pop ecx`. Never a
                             receiver; excluded at the source-kind test.
  * CRT / operator new/delete `_fopen`, `_srand`, `??2`, `??3` cannot be
                             members; the free-callee filter keeps them out of
                             the default screen but they are what
                             `--all-callees` prints.

The 2026-08-23 sweep of the 675-row sub-100 queue: 243 asymmetric ECX sites
over 49 callees unfiltered, 2 after the filters, and BOTH were real -
`CRezArchive::UnpackTag` (the mirror of the already-member
`CRezArchive::PackTag`, and retail hands it ImportDirectoryTree' own spilled `this`)
and `CGameLevel::InflateMainBlock` (retail hands it LoadWwd's `this` in EBP).
Neither callee's bytes moved; both callers gained the load. `--inverse`,
`--receivers` and `--arity` were all zero in the same sweep.

The unfiltered populations are what say the filters are the tool: forward 243
sites over 49 callees, inverse 232 over 50. A defect class does not run both
ways in equal volume - that symmetry IS the register rotation, and 2-versus-0
after the filters is the signal it was hiding.

WHOLE-IMAGE CALIBRATION, 2026-08-23. Run over every paired report row rather
than the sub-100 queue - 4427 rows, of which 3756 score 100.00:

                        EXACT rows            sub-100 rows
    forward   asym      0 callees / 0 sites   40 callees / 171 sites
              hits      0                     0
    inverse   asym      0 callees / 0 sites   63 callees / 232 sites
              hits      0                     0
    --receivers / --arity: 0 in all four cells

The EXACT column is 0 BY CONSTRUCTION and the run proves the implementation
matches the construction: a row at 100.00 is byte-identical to retail, so it
cannot carry an asymmetry, and no caller-diff rule can ever flag it. That is a
statement about THIS SIEVE, not about the code - a dropped receiver lives in an
exact caller perfectly happily (`CBattlezMapConfig::TileSwitch`). Reach those
with `--retail`.

The calibration run also FOUND one detector bug, which is what it is for: ten
of the thirteen inverse sites on exact rows were the caller calling ITSELF. Our
obj spells a recursive call as a `call rel32` with a relocation naming the
function; the delinked target resolves it inside its own section and leaves no
relocation, so the census counted `n/0` on the caller's own name. `_census` now
drops self-referent calls, and both EXACT cells are 0.

RETAIL SCREEN (`--retail`) - the same question with our side deleted.

A function we model FREE has NO receiver by construction, so the paired
"ours-lacks" test carries no information: retail's own bytes decide the row
alone. Dropping our side removes three limits at once - the screen no longer
needs a compare report, no longer needs the caller to be paired or
reconstructed, and no longer needs the caller to be sub-100. The evidence is
one rule over the retail image: at EVERY rel32 call site of the callee (ILT
jmp-thunks expanded one hop), a strict-window ECX definition exists that
NOTHING consumes before the call, and it names an object (member / global /
frame slot / `lea` local / register copy) rather than falling out of
arithmetic.

Measured over the whole free-modelled population, 2026-08-23:

    free-modelled functions                          473
    reachable by a direct retail call site           268
    retail call sites to them                       1225
    ... with any ECX definition in the window        275
    ... of those, DEAD (nothing consumes it)           2
    ... after the object-kind filter                   1     <- the hit

The DEAD filter is the entire sieve: it removes 273 of 275. The noise floor is
directly measurable rather than argued - 147 of the population are library/CRT
free functions that CANNOT be members, they carry 537 call sites, and zero of
those sites show a dead ECX. cl 5.0 does not write a register it will not read.

The one hit is `CBattlezMapConfig::TileSwitch`, which the PAIRED screen cannot
reach: it scored 100.00 EXACT as a free `__stdcall`, and its only caller,
`CBattlezMapConfig::Step`, sits at 87% - far enough from retail that our side
also has an ECX definition in the window, so the `ours-lacks` filter cancels
the row. That is the paired screen's recall limit stated exactly.

The INVERSE of the retail screen is the recall control, not a symmetry
control: of 2854 member-modelled functions with a direct call site, 556 show
NO receiver at any site under this same strict rule. Absence of a detected
receiver therefore means nothing - which is why the forward screen demands
PRESENCE at every site and never argues from a missing one.

`--probe RVA...` runs the screen on named addresses whatever the model says -
the calibration path. Both 2026-08-23 hits (`0x13b970`, `0x160790`) reproduce
under it from the retail image alone.

THE CLASS-LEVEL SOURCE SCREEN IS A CANDIDATE GENERATOR, NOT A SIEVE. Listing
every free function whose FIRST parameter is a modelled class returns 115 rows
image-wide, of which 29 have a direct retail call site and exactly ONE has the
byte evidence. The other 114 are real free functions - object factories
registered as function pointers (`DispatchActionAreaLogic(CGameObject*)` and its
forty siblings), MFC's `AfxCallWndProc`/`ConstructElements`, serializers. A
leading class pointer is not a dropped receiver; the receiver-shaped ECX write
at the call site is. Note also that neither 2026-08-23 hit had a leading class
parameter at all - the receiver was simply ABSENT from the model - so the
source screen cannot see the shape it was proposed to find.

EH FUNCLETS PAIR BY CONSTRUCTION; the earlier claim here that they cannot was
wrong on both counts. cl 5.0 does NOT emit them inside the parent's COMDAT and
they are NOT unnamed: they get their own `.text` COMDAT, carrying cl's local
labels (`$L42015`, `$L42016`, ... at an 11-byte stride), and the normalizer's
`<unit>.symbols.tsv` records the canonical `__ehunwind$<parent>$<n>` name plus
the (section, offset) for each. `rom1 walls ehactions --census` pairs them
that way. The part that survives is the conclusion: a funclet's only transfer
is a destructor tail-call, whose receiver both sides load, so the receiver
sieve over the EH band is empty by construction.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict

from rom1.delink.coffx import Obj
from rom1.walls import check_unit
from rom1.walls.diagnose import _find_function, _locate
from rom1.walls.semdiff import NORM, _decode

BYTES_ONLY = re.compile(r"^(?:[0-9a-f]{2} ?)+$")
ECX_TOK = re.compile(r"\b(ecx|cx|cl|ch)\b")
BRANCH = re.compile(r"^j\w+$")
DIRECT_CALL = re.compile(r"^call\s+0x[0-9a-f]+$")
#: `mov ecx,[<base>+0xNN]` with base a non-frame register: a member read
MEMBER_LOAD = re.compile(
    r"^mov\s+ecx,(?:DWORD PTR )?\[(e[a-d]x|e[sd]i|ebx|ecx)"
    r"(?:\+e[a-z]{2}\*\d)?([+-]0x[0-9a-f]+)?\]$")
FRAME_LOAD = re.compile(
    r"^mov\s+ecx,(?:DWORD PTR )?\[(esp|ebp)([+-]0x[0-9a-f]+)?\]$")
ABS_LOAD = re.compile(r"^mov\s+ecx,(?:DWORD PTR )?(?:ds:)?0x[0-9a-f]+$")
LEA_LOCAL = re.compile(r"^lea\s+ecx,\[(esp|ebp)([+-]0x[0-9a-f]+)?\]$")
LEA_OTHER = re.compile(r"^lea\s+ecx,")
REG_COPY = re.compile(r"^mov\s+ecx,(e[a-d]x|e[sd]i|ebx|ebp)$")
#: cl 5.0 spells `add esp,4` as `pop ecx`. NEVER a receiver.
POP_ECX = re.compile(r"^pop\s+ecx$")
#: an MSVC5 `__thiscall` member mangling - `@` + access + cv + the E convention
THISCALL = re.compile(r"@[QAIUEMB][ABCD]E")

#: instructions back from the call the retail-side scan considers; our side
#: gets three times this because it walks whole blocks
WINDOW = 24
#: ECX sources that name a concrete object, so a hit says WHICH class
STRONG = ("member", "global", "lea-local")


def kind_of(asm: str) -> str:
    """What the ECX definition reads - `pop` is the one that is never a `this`."""
    if POP_ECX.match(asm):
        return "pop"
    if MEMBER_LOAD.match(asm):
        return "member"
    if ABS_LOAD.match(asm):
        return "global"
    if FRAME_LOAD.match(asm):
        return "frame"
    if LEA_LOCAL.match(asm):
        return "lea-local"
    if LEA_OTHER.match(asm):
        return "lea"
    if REG_COPY.match(asm):
        return "regcopy"
    if asm.startswith(("xor ecx,ecx", "sub ecx,ecx")):
        return "zero"
    return "other"


def writes_ecx(asm: str) -> bool:
    parts = asm.split(None, 1)
    if parts[0] in ("cmp", "test", "push", "call", "ret", "nop", "int3"):
        return False
    if len(parts) < 2:
        return False
    return parts[1].split(",")[0].strip() in ("ecx", "cx", "cl", "ch")


def reads_ecx(asm: str) -> bool:
    """ECX appears as a VALUE - a source operand or an address base."""
    parts = asm.split(None, 1)
    if len(parts) < 2:
        return bool(ECX_TOK.search(asm))
    op, rest = parts
    ops = [o.strip() for o in rest.split(",")]
    if op in ("cmp", "test", "push", "xchg"):
        return bool(ECX_TOK.search(rest))
    if writes_ecx(asm):
        if op in ("mov", "lea", "movsx", "movzx", "pop", "set"):
            return any(ECX_TOK.search(s) for s in ops[1:])
        if asm.startswith(("xor ecx,ecx", "sub ecx,ecx")):
            return False        # an idempotent zero, not a use of the old value
        return True
    return bool(ECX_TOK.search(rest))


def branch_targets(lines) -> set[int]:
    out = set()
    for ln in lines:
        asm = ln.asm
        if not asm or not BRANCH.match(asm.split()[0]):
            continue
        m = re.search(r"\b0x([0-9a-f]+)$", asm)
        if m:
            out.add(int(m.group(1), 16))
    return out


def receiver(lines, i: int, targets: set[int], loose: bool = False):
    """The ECX definition reaching call `i`, or None.

    `loose` is the our-side rule: walk back past branch boundaries to the
    previous `call`, so a receiver materialised before a guard branch counts.
    """
    consumed = False
    steps = 0
    limit = WINDOW * 3 if loose else WINDOW
    for j in range(i - 1, -1, -1):
        asm = lines[j].asm
        if not asm or BYTES_ONLY.match(asm):
            continue
        op = asm.split()[0]
        if op in ("call", "ret", "leave"):
            return None                        # ECX is volatile across a call
        if not loose and BRANCH.match(op):
            return None
        if writes_ecx(asm):
            k = kind_of(asm)
            return None if k == "pop" else {
                "kind": k, "asm": asm, "dist": steps, "consumed": consumed,
                "ref": lines[j].ref or ""}
        if reads_ecx(asm):
            consumed = True
        steps += 1
        if steps >= limit or (not loose and lines[j].addr in targets):
            return None
    return None


def call_sites(lines, loose: bool = False) -> list[dict]:
    targets = branch_targets(lines)
    out = []
    for i, ln in enumerate(lines):
        asm = ln.asm
        if not asm or not asm.startswith("call"):
            continue
        out.append({"addr": ln.addr, "ref": ln.ref or "",
                    "direct": bool(DIRECT_CALL.match(asm)),
                    "recv": receiver(lines, i, targets, loose)})
    return out


class _Pin:
    """A (unit, name) the Model cannot resolve - an EH funclet, whose symbol
    carries no rva of its own."""

    def __init__(self, unit, name):
        self.unit, self.name = unit, name


def _pair(token, unit: str | None = None):
    if unit is not None:
        binding = _Pin(unit, token)
    else:
        binding, why = _locate(token)
        if binding is None:
            raise SystemExit(f"[thisscan] {why}")
    base = Obj(NORM / "base" / f"{binding.unit}.obj")
    tp = NORM / "target" / f"{binding.unit}.c.obj"
    if not tp.exists():
        tp = NORM / "target" / f"{binding.unit}.obj"
    bb, brel, _ = _find_function(base, binding.name)
    tb, trel, _ = _find_function(Obj(tp), binding.name)
    return (binding, _decode(bb, brel, binding.name),
            _decode(tb, trel, binding.name))


#: a register name is an allocation accident; the DISPLACEMENT is the model
REGNAME = re.compile(r"\b(?:e[a-d]x|e[sd]i|ebx|ebp)\b")


def _shape(asm: str) -> str:
    """The ECX definition with register names cancelled - `mov ecx,[esi+0x60]`
    and `mov ecx,[edi+0x60]` are the same receiver, `[esi+0x54]` is not."""
    return REGNAME.sub("r", asm.replace("ecx", "@", 1)).replace("@", "ecx", 1)


def _census(cs, self_name: str = ""):
    """(calls, calls-with-a-receiver, receivers) per direct callee.

    A RECURSIVE call is dropped. Our obj spells it as a `call rel32` carrying a
    relocation that names the function, while the delinked target resolves the
    same call inside its own section and leaves no relocation - so the two
    sides count `n/0` on the caller's own name and every self-recursive
    function reads as an asymmetry it does not have. Ten of the thirteen
    inverse sites in the 2026-08-23 whole-image sweep were exactly this, all of
    them on rows scoring 100.00.
    """
    tot, rec, det = Counter(), Counter(), defaultdict(list)
    for c in cs:
        if not c["direct"] or not c["ref"] or c["ref"] == self_name:
            continue
        tot[c["ref"]] += 1
        if c["recv"]:
            rec[c["ref"]] += 1
            det[c["ref"]].append(c["recv"])
    return tot, rec, det


def scan_one(token: str, unit: str | None = None, inverse: bool = False) -> dict:
    binding, lb, lt = _pair(token, unit)
    # the side that must show the receiver gets the STRICT rule, the side that
    # must lack it gets the weaker one
    ours = call_sites(lb, loose=not inverse)
    retail = call_sites(lt, loose=inverse)
    give, lack = ((retail, ours) if not inverse else (ours, retail))
    tg, rg, dg = _census(give, binding.name)
    tl, rl, _dl = _census(lack, binding.name)

    hits, asym = [], []
    for ref in sorted(tg):
        if rg[ref] == 0 or rg[ref] <= rl[ref]:
            continue
        rs = dg[ref]
        rec = {"callee": ref, "n": tg[ref], "other_n": tl[ref],
               "recv": rg[ref], "other_recv": rl[ref],
               "kinds": sorted({r["kind"] for r in rs}),
               "strong": sum(1 for r in rs if r["kind"] in STRONG),
               "dead": all(not r["consumed"] for r in rs),
               "maxdist": max(r["dist"] for r in rs),
               "asm": sorted({r["asm"] for r in rs}),
               "thiscall": bool(THISCALL.search(ref))}
        asym.append(rec)
        if (tg[ref] == tl[ref] and rl[ref] == 0 and rg[ref] == tg[ref]
                and rec["dead"] and not rec["thiscall"]):
            hits.append(rec)
    seq_o = [c["ref"] for c in ours if c["direct"]]
    seq_r = [c["ref"] for c in retail if c["direct"]]
    return {"hits": hits, "asym": asym, "ordered": seq_o == seq_r and bool(seq_o),
            "calls": len(seq_o),
            # the mismatch screen needs the SAME rule on both sides - the
            # asymmetric pair above would read a further-back our-side
            # definition as a different object
            "mismatch": _receiver_mismatch(call_sites(lb), call_sites(lt),
                                           seq_o == seq_r),
            "arity": _arity_mismatch(lb, lt, seq_o == seq_r)}


#: caller-side cleanup of a `__cdecl` call. cl 5.0 spells `add esp,4` as
#: `pop ecx`, and merges the cleanup of adjacent calls.
CLEANUP = re.compile(r"^add\s+esp,(0x[0-9a-f]+)$")


def _cleanups(lines) -> list[tuple[str, int | None]]:
    """(callee, bytes the CALLER pops) for each direct call, in order.

    None where the next instruction is not a cleanup - a `__stdcall` callee, a
    merged cleanup, or a deferred one.
    """
    out = []
    for i, ln in enumerate(lines):
        if not ln.asm or not DIRECT_CALL.match(ln.asm):
            continue
        nxt = None
        for j in range(i + 1, len(lines)):
            a = lines[j].asm
            if not a or BYTES_ONLY.match(a):
                continue
            m = CLEANUP.match(a)
            if m:
                nxt = int(m.group(1), 16)
            elif a == "pop ecx":
                nxt = 4
            break
        out.append((ln.ref or "", nxt))
    return out


def _arity_mismatch(lb, lt, ordered) -> list[dict]:
    """`__cdecl` argument-count defects.

    A `__cdecl` callee does not clean up, so a trailing argument it never reads
    is invisible in ITS bytes - the caller's `add esp,N` is the only witness,
    exactly as ECX is the only witness of a dropped receiver.
    """
    if not ordered:
        return []
    out = []
    for (ra, ca), (rb, cb) in zip(_cleanups(lb), _cleanups(lt)):
        if ca is None or cb is None or ca == cb:
            continue
        out.append({"callee": ra, "ours": ca, "retail": cb})
    return out


def _receiver_mismatch(ours, retail, ordered) -> list[dict]:
    """Call sites where BOTH sides pass a receiver but from a DIFFERENT member
    or global - a wrong-object bug, not a missing-argument one.

    The callee must be mangled `__thiscall`. Against a FREE callee ECX is an
    ordinary scratch register, so the "receiver" is whichever step of a pointer
    chain happened to land there - all five rows of the first sweep were that
    (`[g_gameReg+0x30]` then `[+0x24]` then `[+0x5c]`, with the two sides
    stopping at different links). Only member-vs-member and global-vs-global
    are reported: a register copy (`mov ecx,esi`) names no object.
    """
    if not ordered:
        return []
    po = [c for c in ours if c["direct"]]
    pr = [c for c in retail if c["direct"]]
    out = []
    for a, b in zip(po, pr):
        ra, rb = a["recv"], b["recv"]
        if not ra or not rb or ra["kind"] != rb["kind"]:
            continue
        if not THISCALL.search(a["ref"]):
            continue
        if ra["kind"] == "member" and _shape(ra["asm"]) != _shape(rb["asm"]):
            out.append({"callee": a["ref"], "kind": "member",
                        "ours": _shape(ra["asm"]), "retail": _shape(rb["asm"])})
        elif ra["kind"] == "global" and ra["ref"] != rb["ref"]:
            out.append({"callee": a["ref"], "kind": "global",
                        "ours": ra["ref"] or "(none)",
                        "retail": rb["ref"] or "(none)"})
    return out


def scan(rows, inverse: bool, progress=None) -> list[dict]:
    out = []
    for n, row in enumerate(rows, 1):
        rec = {k: row[k] for k in ("rva", "unit", "symbol", "cur", "hist_max")}
        try:
            try:
                rec.update(scan_one(row["rva"], inverse=inverse))
            except SystemExit:
                rec.update(scan_one(row["symbol"], row["unit"], inverse))
        except BaseException as err:
            # mostly an EH funclet: it has no rva in the Model and no
            # `__ehunwind$` symbol in OUR coff, only cl's `$L<n>` label. It
            # pairs through the normalizer's canonical map - see
            # `walls ehactions --census` - and its receiver population is
            # empty by construction, so this sieve does not chase it.
            rec["skipped"] = str(err)[:110]
        out.append(rec)
        if progress and n % 100 == 0:
            print(f"  ... {n}/{len(rows)}", file=progress)
    return out


def report_mismatch(rows, limit: int) -> None:
    ok = [r for r in rows if "mismatch" in r]
    hit = [r for r in ok if r["mismatch"]]
    sites = sum(len(r["mismatch"]) for r in hit)
    print(f"paired rows read: {len(ok)}   "
          f"(skipped {len(rows) - len(ok)}: EH funclets - pair them with "
          "`walls ehactions --census`, whose receiver population is "
          "empty by construction)")
    print(f"  callers passing a receiver from a DIFFERENT member/global : "
          f"{len(hit)}")
    print(f"  call SITES                                               : "
          f"{sites}")
    print("  a `lea`-folded base shifts the displacement without changing the "
          "object - compare the SUM before believing a row.")
    print()
    for r in sorted(hit, key=lambda x: -x["cur"])[:limit]:
        print(f"{r['rva']} {r['cur']:6.2f} (hist {r['hist_max'] or 0:6.2f}) "
              f"{r['unit']}/{r['symbol'][:64]}")
        for m in r["mismatch"]:
            print(f"    -> {m['callee'][:74]}")
            print(f"       {m['kind']}  ours {m['ours']}   retail {m['retail']}")


def report_arity(rows, limit: int) -> None:
    ok = [r for r in rows if "arity" in r]
    hit = [r for r in ok if r["arity"]]
    sites = sum(len(r["arity"]) for r in hit)
    print(f"paired rows read: {len(ok)}   "
          f"(skipped {len(rows) - len(ok)}: EH funclets - pair them with "
          "`walls ehactions --census`, whose receiver population is "
          "empty by construction)")
    print(f"  callers whose `__cdecl` cleanup differs from retail's : {len(hit)}")
    print(f"  call SITES                                            : {sites}")
    print("  cl merges the cleanup of adjacent calls and can defer one, so read "
          "the surrounding\n  run before believing a row is an argument-count "
          "defect.")
    print()
    for r in sorted(hit, key=lambda x: -x["cur"])[:limit]:
        print(f"{r['rva']} {r['cur']:6.2f} (hist {r['hist_max'] or 0:6.2f}) "
              f"{r['unit']}/{r['symbol'][:64]}")
        for m in r["arity"]:
            print(f"    -> {m['callee'][:74]}")
            print(f"       ours pops 0x{m['ours']:x}   retail pops "
                  f"0x{m['retail']:x}")


def report(rows, limit: int, inverse: bool, all_callees: bool) -> None:
    ok = [r for r in rows if "hits" in r]
    key = "asym" if all_callees else "hits"
    hit = [r for r in ok if r[key]]
    sites = sum(h["n"] for r in hit for h in r[key])
    dead = sum(h["n"] for r in hit for h in r[key] if h["dead"])
    strong = sum(h["strong"] for r in hit for h in r[key])
    free = sum(h["n"] for r in hit for h in r[key] if not h["thiscall"])
    callees = {h["callee"] for r in hit for h in r[key]}
    who = "WE pass" if inverse else "retail passes"
    print(f"paired rows read: {len(ok)}   "
          f"(skipped {len(rows) - len(ok)}: EH funclets - pair them with "
          "`walls ehactions --census`, whose receiver population is "
          "empty by construction)")
    print(f"  callers where {who} a receiver the other side lacks")
    print(f"    callers                                 : {len(hit):4d}")
    print(f"    call SITES                              : {sites:4d}")
    print(f"    ... ECX value never consumed            : {dead:4d}")
    print(f"    ... ECX from a member/global/local      : {strong:4d}")
    print(f"    ... callee not already thiscall         : {free:4d}")
    print(f"    distinct CALLEES named                  : {len(callees):4d}")
    print()
    for r in sorted(hit, key=lambda x: -x["cur"])[:limit]:
        print(f"{r['rva']} {r['cur']:6.2f} (hist {r['hist_max'] or 0:6.2f}) "
              f"{r['unit']}/{r['symbol'][:64]}"
              + ("" if r["ordered"] else "   [call order differs]"))
        for h in r[key]:
            print(f"    -> {'[member]' if h['thiscall'] else '[FREE]  '} "
                  f"{h['callee'][:74]}")
            print(f"       n={h['n']}/{h['other_n']} recv={h['recv']}/"
                  f"{h['other_recv']} kind={','.join(h['kinds'])} "
                  f"dead={h['dead']} dist<={h['maxdist']}  "
                  f"{' | '.join(h['asm'])}")
    if not all_callees:
        return
    print("\nCALLEE census (distinct callers naming each):")
    per = Counter()
    for r in hit:
        for h in r[key]:
            per[h["callee"]] += 1
    for c, n in per.most_common(80):
        print(f"  {n:3d}  {c}")


# --------------------------------------------------------------------------
# the RETAIL screen: the same question with our side deleted
# --------------------------------------------------------------------------

#: free by mangling. `@@YI` is free __FASTCALL - its first integer argument
#: rides in ECX by ABI, so a `mov ecx,..` before the call is that argument.
FREE_CONV = re.compile(r"@@Y[AGJ]")
#: a STATIC member (`@@SA`/`@@SG`): a class member that takes no receiver, so
#: it belongs in the free population as a control rather than a candidate.
STATIC_MEMBER = re.compile(r"@[0-9A-Z_]*@@S[AG]")


def _retail_lines(img, owner, cache):
    if owner.rva not in cache:
        from rom1.tool import objdump
        body = img.read(owner.rva, owner.size or 0x40)
        out = []
        for line in (objdump.disassemble(body, vma=owner.rva).splitlines()
                     if body else ()):
            if ":\t" not in line:
                continue
            head, rest = line.split(":\t", 1)
            try:
                addr = int(head.strip(), 16)
            except ValueError:
                continue
            parts = rest.split("\t")
            out.append((addr, " ".join(
                (parts[-1] if len(parts) > 1 else parts[0]).split())))
        cache[owner.rva] = out
    return cache[owner.rva]


def _retail_receiver(lines, site):
    """The ECX definition reaching the retail call at `site`, strict rule."""
    i = next((k for k, (a, _s) in enumerate(lines) if a == site), None)
    if i is None:
        return None
    consumed = False
    for steps, j in enumerate(range(i - 1, -1, -1)):
        asm = lines[j][1]
        if not asm or BYTES_ONLY.match(asm):
            continue
        op = asm.split()[0]
        if op in ("call", "ret", "leave") or BRANCH.match(op):
            return None
        if writes_ecx(asm):
            k = kind_of(asm)
            return None if k == "pop" else {
                "kind": k, "asm": asm, "consumed": consumed, "dist": steps}
        if reads_ecx(asm):
            consumed = True
        if steps >= WINDOW:
            return None
    return None


#: an ECX definition that NAMES an object. `and ecx,0x3` reaches the call with
#: nothing consuming it and is still not a receiver - it is arithmetic that
#: happened to land in ECX (measured on `?FileExists@@YAHPBD@Z`).
OBJECT_KINDS = ("member", "global", "frame", "lea-local", "regcopy")


def retail_screen(img, idx, rva, name, unit, cache):
    """One callee: what retail hands it in ECX at every rel32 call site."""
    entries = [rva] + img.thunks_to(rva)
    sites = sorted({s for e in entries
                    for s, op in img.call_index.get(e, ()) if op == 0xE8})
    rec = {"rva": f"0x{rva:06x}", "unit": unit, "name": name,
           "sites": len(sites), "recv": 0, "dead": 0, "named": 0,
           "consumed": 0, "none": 0, "outside": 0, "kinds": Counter(),
           "where": []}
    for site in sites:
        owner = idx.owner(site)
        if owner is None or owner.rva == rva:
            rec["outside"] += 1                 # a tail in nobody's extent
            continue
        r = _retail_receiver(_retail_lines(img, owner, cache), site)
        if r is None:
            rec["none"] += 1
            continue
        rec["recv"] += 1
        rec["kinds"][r["kind"]] += 1
        if r["consumed"]:
            rec["consumed"] += 1
            continue
        rec["dead"] += 1
        if r["kind"] not in OBJECT_KINDS:
            continue
        rec["named"] += 1
        if len(rec["where"]) < 6:
            rec["where"].append(f"0x{site:06x} in "
                                f"{(owner.name or '')[:56]}   {r['asm']}")
    rec["kinds"] = dict(rec["kinds"])
    rec["hit"] = bool(sites and not rec["outside"]
                      and rec["named"] == rec["sites"])
    return rec


def retail_main(probe, limit: int, as_json: bool) -> int:
    from rom1.model import resolve
    from rom1.sema.image import retail
    from rom1.sema.index import index
    idx, img, cache = index(), retail(), {}
    if probe:
        for tok in probe:
            rva = int(tok, 16)
            b = idx.func(rva)
            json.dump(retail_screen(img, idx, rva, b.name if b else "?",
                                    b.unit if b else "?", cache),
                      sys.stdout, indent=1)
            print()
        return 0

    free, member, rows = [], [], []
    for b in resolve().functions:
        if not b.name or not b.name.startswith("?") or "@@YI" in b.name:
            continue
        if FREE_CONV.search(b.name) or STATIC_MEMBER.search(b.name):
            free.append(b)
        elif THISCALL.search(b.name):
            member.append(b)
    for b in free:
        rows.append(retail_screen(img, idx, b.rva, b.name, b.unit, cache))
    reach = [r for r in rows if r["sites"] and not r["outside"]]
    hits = [r for r in reach if r["hit"]]
    lib = [r for r in rows if not r["unit"]]
    # a callee with no `call` site is NOT a blind spot when retail STORES its
    # address: a __thiscall member cannot be a plain function pointer, so an
    # address-taken callee is free by its own usage. What is left is reached by
    # nothing at all, and has no witness of any kind.
    taken = 0
    for r in rows:
        if r["sites"]:
            continue
        rva = int(r["rva"], 16)
        if (any(t == rva for _s, t in img.refs_to_range(rva, rva + 1))
                or img.thunks_to(rva)):
            taken += 1
    unreached = sum(1 for r in rows if not r["sites"])

    if as_json:
        json.dump(rows, sys.stdout)
        return 0
    print("RETAIL screen: what retail hands a FREE-modelled callee in ECX.")
    print("Our side has no receiver by construction, so retail's bytes decide "
          "the row\nalone - no compare report, no pairing, no score.\n")
    print(f"  free-modelled functions            : {len(rows):5d}")
    print(f"  reachable by a direct call site    : {len(reach):5d}")
    print(f"  retail call sites to them          : "
          f"{sum(r['sites'] for r in reach):5d}")
    print(f"  ... with an ECX definition         : "
          f"{sum(r['recv'] for r in reach):5d}")
    print(f"  ... of those DEAD (nothing reads it): "
          f"{sum(r['dead'] for r in reach):5d}")
    print(f"  ... and NAMING an object           : "
          f"{sum(r['named'] for r in reach):5d}")
    print(f"  callees flagged at EVERY site      : {len(hits):5d}")
    partial = [r for r in reach if r["named"] and not r["hit"]]
    print(f"  ... at SOME sites only             : {len(partial):5d}   "
          "read these by hand: the strict rule stops at a branch, so a "
          "receiver\n                                              retail "
          "materialises before a guard reads as absent")
    for r in sorted(partial, key=lambda x: -x["named"] / x["sites"])[:limit]:
        print(f"      {r['rva']} {r['named']}/{r['sites']} {r['unit']:18} "
              f"{r['name'][:56]}")
    print(f"\n  no direct call site                : {unreached:5d}")
    print(f"  ... but ADDRESS-TAKEN in retail    : {taken:5d}   free by its "
          "own usage - a member cannot be a plain function pointer")
    print(f"  ... reached by nothing at all      : {unreached - taken:5d}   "
          "undecidable: no witness exists")
    print(f"\n  noise floor: {len(lib)} library/CRT free functions that CANNOT "
          f"be members\n  carry {sum(r['sites'] for r in lib)} call sites and "
          f"{sum(r['dead'] for r in lib)} dead-ECX site(s).\n")
    for r in sorted(hits, key=lambda x: -x["sites"])[:limit]:
        print(f"{r['rva']} {r['unit']:22} {r['name'][:66]}  "
              f"sites={r['sites']}")
        for w in r["where"]:
            print(f"    {w}")
    print(f"\nrecall control (NOT a symmetry control): of {len(member)} "
          f"member-modelled functions,\n  the same strict rule finds NO "
          "receiver at any site for a large minority -\n  absence of a "
          "detected receiver is not evidence. Run --json and count if you "
          "need\n  the number for a specific build.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls thisscan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("--retail", action="store_true",
                    help="the score-free screen: retail's own call sites to "
                         "every FREE-modelled callee. Needs no compare report "
                         "and reaches callers the paired screen cannot")
    ap.add_argument("--probe", nargs="+", metavar="RVA",
                    help="run the retail screen on these addresses whatever "
                         "the model says they are (calibration)")
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true",
                    help="the campaign queue rather than every sub-100 row")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--above", type=float, default=-1.0,
                    help="calibration: exact rows are byte-identical, so any "
                         "hit at --above 100 --below 100.01 is a detector bug")
    ap.add_argument("--inverse", action="store_true",
                    help="the mirror: WE pass a receiver retail does not")
    ap.add_argument("--all-callees", action="store_true",
                    help="print every asymmetric callee, filters off")
    ap.add_argument("--arity", action="store_true",
                    help="the `__cdecl` argument-count screen: our caller's "
                         "`add esp,N` against retail's. A trailing argument a "
                         "__cdecl callee ignores is invisible in ITS bytes")
    ap.add_argument("--receivers", action="store_true",
                    help="the adjacent screen: BOTH sides pass a receiver, but "
                         "from a different member or global (a wrong-OBJECT "
                         "bug rather than a missing-argument one)")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--one", help="a single rva or name")
    args = ap.parse_args(argv)

    if args.retail or args.probe:
        return retail_main(args.probe, args.limit, args.json)
    if args.one:
        json.dump(scan_one(args.one, inverse=args.inverse), sys.stdout, indent=1)
        print()
        return 0
    from rom1.walls.inventory import build
    rows = build(check_unit(args.unit), args.below, args.todo)
    if args.above >= 0:
        rows = [r for r in rows if r["cur"] >= args.above]
    scanned = scan(rows, args.inverse, None if args.json else sys.stderr)
    if args.json:
        json.dump(scanned, sys.stdout)
        return 0
    if args.arity:
        report_arity(scanned, args.limit)
    elif args.receivers:
        report_mismatch(scanned, args.limit)
    else:
        report(scanned, args.limit, args.inverse, args.all_callees)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
