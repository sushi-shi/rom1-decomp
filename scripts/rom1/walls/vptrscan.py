"""rom1.walls.vptrscan - the VPTR-STAMP census.

A constructor stamps each of its subobjects' vtables:

    mov DWORD PTR [this+0x70],OFFSET ??_7CObject@@6B@

Two facts live in that one instruction, and NOTHING else in the build reads
either of them. The DISPLACEMENT says which subobject the vptr belongs to; the
RELOCATION says which class the object claims to be. Get the displacement
wrong and a polymorphic member's vptr lands in the neighbouring field - every
virtual call through it dispatches off whatever that field holds. Get the
relocation wrong and the object's dynamic type is another class, so every slot
resolves to the wrong function. Either defect moves TWO BYTES.

WHY NO OTHER CHANNEL SEES IT. `offsetscan` suppressed the whole line until
2026-08-23: a relocated line's displacement is usually a masked link-time
address (`[eax+<g_table>]`), so dropping it is right - except here, where the
relocation is the IMMEDIATE and the displacement is a real member offset.
That suppression is now split by which operand the relocation owns, but the
positional sieve still only reads stamps its ALIGNMENT paired, and a ctor
whose call-set diverges is never aligned. `assert-relocs` proves the referent
resolves, not that it is stamped at the right offset. `vtable_owner --audit`
proves a `VTBL()` binding against RTTI, which is the vtable's own identity,
not the store. And a wrong subobject offset perturbs so few bytes that the
score reads it as regalloc residue.

WHAT IT READS. The COFF bytes, not a disassembly. A stamp is opcode `C7` with
a ModRM whose `reg` field is 0 and a DIR32 relocation sitting in the imm32,
so the relocation site's own address decodes the instruction BACKWARDS with no
ambiguity: each candidate start is re-encoded forward and must end exactly at
the imm32. The whole image reads in about a second, against two objdump
subprocesses per function for the disassembly route.

WHAT IS COUNTED APART, AND WHY:

  * a FRAME-relative stamp (`[esp+N]`, or `[ebp+N]` when the prologue really
    set up a frame pointer). That is a stack-constructed object and N is a
    slot number, which is an output of cl's allocator - `framescan` owns it.
    43 of 1032 stamps.
  * a vtable address materialized into a REGISTER (`mov eax,OFFSET ??_7X`)
    and stored later. The byte scan cannot see which offset it reaches, so
    those are reported as a separate list rather than silently dropped. 42
    sites, all in six functions, and both sides carry the same set.
  * a function only ONE side's object defines. cl emits a COMDAT copy of every
    inline dtor and `??_G` thunk into every TU that needs it, and the retail
    image kept one; 342 of the 349 raw sequence differences are that, and none
    of them is evidence about a stamp.

WHAT THE SWEEP IS WORTH, measured 2026-08-23 over the whole image: 989 stamps
through a non-frame base in functions both objects define, 974 aligned pairs,
ZERO differing in displacement and ZERO differing in vtable symbol. The split
is non-trivial - 18 of those stamps are at a NON-ZERO subobject offset and 228
distinct vtables are stamped - and the MI population the question is really
about (a secondary base's own `??_7C@@6BBase@@@`) is 23 direct stamps plus 3
through a register, matching retail exactly on offset, symbol, function and
count. FOUR rows are withheld, all four an inlining divergence in the stamp
COUNT with every paired stamp at the same offset naming the same vtable: an
extra `CGruntCoordList` in `CGrunt`'s ctor, an extra `CRgn` in
`CRom1Mgr::TransitionState`, a duplicated `CObject` at +0x70 in
`CDDrawWorkerHost::RebuildPlanes`, and a `CResolveNode` retail stamps in
`~CWwdGameObject` that we do not.

THE COMPANION READING, `--slots`. The stamp says the object claims the right
class; the SLOT says the call reaches the right method of it. A virtual
dispatch is `call DWORD PTR [reg+N]` and N is the slot index times four, so a
wrong N calls a different virtual function - and `offsetscan` drops every
`call`/`jmp` line by construction (it is excluding the switch table), so
nothing reads it either. Measured 2026-08-23: 4433 dispatches ours against
4434 retail over 44 distinct slot displacements (deepest +0xe8, slot 58) and
FIVE rows whose multiset differs - none at the same call count, none using a
slot the other side does not, every one a pure count divergence of the same
slots. No site in the tree dispatches through a different slot than retail.
The byte scan finds 28 of those rows and a real disassembly discards 23:
our base object has every `call rel32` displacement zeroed by its relocation
while the delinked target resolves a SELF-call internally, so retail carries
four `ff` bytes that decode as `call DWORD PTR [edi+0xe8]` and we carry four
zeros. `CRezArchiveDir`'s destructor is byte-identical to retail at 100.00 and still
read as a retail-only slot 58 that way, which is why every differing row is
re-read off a decoded stream before it is reported.

    rom1 walls vptrscan [--all] [--json]
    rom1 walls vptrscan --slots [--all]
    rom1 walls vptrscan --control    hermetic positives, negatives, and the
                                       backwards run over the live image
"""

from __future__ import annotations

import argparse
import bisect
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rom1.delink.coffx import Obj
from rom1.walls.semdiff import NORM

#: `??_7C@@6B@` is a vtable, `??_8C@@7B@` a virtual-base table.  Both are
#: stamped into an object and both name a subobject by their store's offset.
VTBL = re.compile(r"^\?\?_[78]")

#: `??_7C@@6BBase@@@` - the vtable of C's SECONDARY base `Base`, which is the
#: population where a wrong subobject offset actually bites
SECONDARY = re.compile(r"^\?\?_[78].+@@[67]B.+@$")

REGS = ("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi")

#: the longest `mov r/m32,imm32` prefix: C7 + ModRM + SIB + disp32
MAX_PREFIX = 7


def decode_store(payload: bytes, imm_off: int):
    """(base, index, disp) of the `mov r/m32,imm32` whose imm32 starts at
    `imm_off`, or None when these bytes are not that instruction.

    Walked backwards: the encoding lengths are fixed, so each candidate start
    is re-encoded forward and accepted only if the instruction ends exactly at
    the imm32. `reg != 0` is some other `C7` group member and `mod == 3` is a
    register destination, neither of which is a stamp.
    """
    for back in range(2, MAX_PREFIX + 1):
        start = imm_off - back
        if start < 0 or payload[start] != 0xC7:
            continue
        modrm = payload[start + 1]
        mod, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
        if reg != 0 or mod == 3:
            continue
        p = start + 2
        base = idx = None
        if rm == 4:                                   # SIB
            if p >= len(payload):
                continue
            sib = payload[p]
            p += 1
            xi, bs = (sib >> 3) & 7, sib & 7
            idx = None if xi == 4 else REGS[xi]
            base = None if (bs == 5 and mod == 0) else REGS[bs]
        elif rm == 5 and mod == 0:
            base = None                               # disp32 absolute
        else:
            base = REGS[rm]
        disp = 0
        if mod == 1:
            if p >= len(payload):
                continue
            disp = int.from_bytes(payload[p:p + 1], "little", signed=True)
            p += 1
        elif mod == 2 or base is None:
            if p + 4 > len(payload):
                continue
            disp = int.from_bytes(payload[p:p + 4], "little", signed=True)
            p += 4
        if p == imm_off:
            return base, idx, disp
    return None


def frame_bases(payload: bytes, at: int) -> frozenset:
    """The registers that really address this body's frame. ESP always; EBP
    only when the prologue set it up, since /O2 omits the frame pointer and
    then EBP is an ordinary value register holding a heap pointer."""
    if payload[at:at + 3] == b"\x55\x8b\xec":
        return frozenset(("esp", "ebp"))
    return frozenset(("esp",))


def scan_obj(path: Path):
    """({fn: [(off, disp, base, referent, frame?)]}, {fn: [(how, reg, ref)]},
    {defined names}) for one object.

    EVERY `mov r/m32,imm32` carrying a DIR32 is collected, not only the ones
    whose referent is a vtable: a stamp whose two sides name DIFFERENT symbols
    is the defect under test, so the pairing has to see both halves.
    """
    obj = Obj(path)
    stamps: dict[str, list] = defaultdict(list)
    viareg: dict[str, list] = defaultdict(list)
    defined: set[str] = set()
    for secnum in range(1, obj.nsec + 1):
        if not (obj.section_table[secnum - 1]["characteristics"] & 0x20):
            continue                                  # not CNT_CODE
        payload = obj.section_payload(secnum)
        if not payload:
            continue
        members = sorted((v, n) for v, n, _s in obj.section_members(secnum))
        defined.update(n for _v, n in members)
        offs = [v for v, _n in members]
        for site, (name, typ) in sorted(obj.typed_relocations(secnum).items()):
            if typ != 6:                              # DIR32
                continue
            i = bisect.bisect_right(offs, site) - 1
            fn, at = (members[i][1], members[i][0]) if i >= 0 else (None, 0)
            dec = decode_store(payload, site)
            if dec:
                base, _idx, disp = dec
                stamps[fn].append((site - at, disp, base, name,
                                   base in frame_bases(payload, at)))
            elif VTBL.match(name):
                if site and 0xB8 <= payload[site - 1] <= 0xBF:
                    viareg[fn].append(("materialize",
                                       REGS[payload[site - 1] - 0xB8], name))
                elif site and payload[site - 1] == 0x68:
                    viareg[fn].append(("push", None, name))
                else:
                    viareg[fn].append(("other", None, name))
    return stamps, viareg, defined


def load(side: str, root: Path | None = None):
    root = (root or NORM) / side
    stamps, viareg, defs = {}, {}, {}
    for path in sorted(root.glob("*.obj")):
        unit = path.name.split(".")[0]
        st, vr, dd = scan_obj(path)
        defs[unit] = dd
        for fn, v in st.items():
            stamps[(unit, fn)] = v
        for fn, v in vr.items():
            viareg[(unit, fn)] = v
    return stamps, viareg, defs


def _paired(o: list, r: list, keyidx: int):
    """Positions the two stamp lists agree on when aligned by ONE field.

    The alignment key can never be the field under test: keying on the
    referent and then asking whether the referent differs is a tautology, and
    measured on a real object it is worse than useless - re-pointing one
    relocation made difflib delete-and-insert, re-pair the neighbours, and
    report TWO wrong offsets where one vtable symbol had moved. So each defect
    kind is read from the alignment that does NOT use it.
    """
    sm = difflib.SequenceMatcher(a=[s[keyidx] for s in o],
                                 b=[s[keyidx] for s in r], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            yield from zip(range(i1, i2), range(j1, j2))


def compare(ours: dict, retail: dict, both: set):
    """(rows, aligned pairs, offset defects, vtable defects).

    Each reading is GATED on its own key's multiset agreeing. Keying on the
    referent and reading the displacement is sound only while both sides stamp
    the same referents - once one referent moves, difflib deletes and inserts,
    re-pairs the neighbours, and reports wrong offsets that are not there
    (measured: re-pointing ONE relocation in a real object produced two). So a
    row whose referent multiset differs has its offset reading WITHHELD, and a
    row whose displacement multiset differs has its vtable reading withheld.
    Each defect kind still fires, because a defect perturbs one key and leaves
    the other intact; what is lost is a row carrying BOTH at once, which is
    reported as withheld rather than adjudicated wrongly.
    """
    rows, aligned, off_bad, sym_bad = [], 0, 0, 0
    for k in sorted(both):
        o = [s for s in ours.get(k, ()) if not s[4]]
        r = [s for s in retail.get(k, ()) if not s[4]]
        if not any(VTBL.match(s[3]) for s in o + r):
            continue
        bad, withheld = [], []
        if Counter(s[3] for s in o) == Counter(s[3] for s in r):
            for i, j in _paired(o, r, 3):
                aligned += 1
                if o[i][1] != r[j][1]:
                    off_bad += 1
                    bad.append(("offset", o[i], r[j]))
        else:
            withheld.append("offset")
        if Counter(s[1] for s in o) == Counter(s[1] for s in r):
            for i, j in _paired(o, r, 1):
                if o[i][3] != r[j][3]:
                    sym_bad += 1
                    bad.append(("vtable", o[i], r[j]))
        else:
            withheld.append("vtable")
        if bad or withheld:
            rows.append({"unit": k[0], "symbol": k[1], "bad": bad,
                         "withheld": withheld, "ours": o, "retail": r})
    return rows, aligned, off_bad, sym_bad


def sweep(root: Path | None = None):
    ours, ours_reg, ours_def = load("base", root)
    retail, retail_reg, retail_def = load("target", root)
    both = {(u, n) for u, ns in ours_def.items() for n in ns
            if n in retail_def.get(u, ())}
    rows, aligned, off_bad, sym_bad = compare(ours, retail, both)
    return {"rows": rows, "aligned": aligned, "offset_defects": off_bad,
            "vtable_defects": sym_bad, "both": both,
            "ours": ours, "retail": retail,
            "ours_reg": ours_reg, "retail_reg": retail_reg}


def _counts(acc, both):
    heap = [s for k in both for s in acc.get(k, ()) if VTBL.match(s[3])
            and not s[4]]
    frame = [s for k in both for s in acc.get(k, ()) if VTBL.match(s[3])
             and s[4]]
    return heap, frame


def report(res, show_all: bool) -> None:
    both = res["both"]
    oh, of_ = _counts(res["ours"], both)
    rh, rf = _counts(res["retail"], both)
    print(f"functions both objects define : {len(both)}")
    print(f"vtable stamps through a non-frame base : ours {len(oh)}, "
          f"retail {len(rh)}")
    print(f"  (frame-relative, framescan's channel : ours {len(of_)}, "
          f"retail {len(rf)})")
    print(f"  via a register, offset unreadable    : ours "
          f"{sum(len(v) for k, v in res['ours_reg'].items() if k in both)}, "
          f"retail "
          f"{sum(len(v) for k, v in res['retail_reg'].items() if k in both)}")
    for tag, heap in (("ours", oh), ("retail", rh)):
        hist = Counter(s[1] for s in heap)
        nz = sum(n for d, n in hist.items() if d)
        print(f"  {tag:6s}: {len(set(s[3] for s in heap))} distinct vtables, "
              f"{nz} stamp(s) at a NON-ZERO subobject offset "
              f"({', '.join(f'+0x{d:x} x{n}' for d, n in sorted(hist.items()) if d)})")
    for tag, acc, reg in (("ours", res["ours"], res["ours_reg"]),
                          ("retail", res["retail"], res["retail_reg"])):
        n = sum(1 for k in both for s in acc.get(k, ())
                if SECONDARY.match(s[3]) and not s[4])
        m = sum(1 for k in both for s in reg.get(k, ())
                if SECONDARY.match(s[2]))
        print(f"  {tag:6s}: {n} SECONDARY-base stamp(s) direct, {m} via a register")
    print()
    print(f"aligned stamp pairs read : {res['aligned']}")
    print(f"  stamped at a DIFFERENT member offset : {res['offset_defects']}")
    print(f"  stamping a DIFFERENT vtable          : {res['vtable_defects']}")
    real = [r for r in res["rows"] if r["bad"]]
    held = [r for r in res["rows"] if r["withheld"] and not r["bad"]]
    print(f"rows carrying a defect               : {len(real)}")
    print(f"rows the sieve WITHHELD              : {len(held)}   (the stamp "
          f"multiset itself differs, so the alignment key is not trustworthy - "
          f"an inlining divergence, to be read by hand)")
    for r in (res["rows"] if show_all else real):
        print(f"\n  {r['unit']}/{r['symbol'][:66]}"
              + (f"   [withheld: {', '.join(r['withheld'])}]"
                 if r["withheld"] else ""))
        for why, o, t in r["bad"]:
            print(f"    {why:7s} ours +0x{o[1]:x} {o[3]}")
            print(f"    {'':7s} retail +0x{t[1]:x} {t[3]}")
        if show_all and not r["bad"]:
            print(f"    ours   {[(hex(s[1]), s[3]) for s in r['ours']]}")
            print(f"    retail {[(hex(s[1]), s[3]) for s in r['retail']]}")


#: a vtable slot is a pointer index, so its displacement is a multiple of 4,
#: and no class in the image has a vtable anywhere near this long. Both bounds
#: exist because this is a BYTE scan: `ff` occurs inside other instructions'
#: operands, and an unfiltered sweep read `call [reg+83]` and `call
#: [reg+0x90909090]` as slots and reported three same-count "defects" that were
#: all misalignments.
MAX_SLOT = 0x400


def dispatches(payload: bytes, lo: int, hi: int, relocs: set, frame: set):
    """[(offset, 'call'|'jmp', base, slot displacement)] in one function.

    `FF /2` is `call r/m32` and `FF /4` is `jmp r/m32`; `mod == 3` is a
    register operand (`call eax`, no slot), a disp32 carrying a RELOCATION is a
    global or an import thunk rather than a vtable, and a frame-relative base
    is a stack slot.
    """
    out = []
    i = lo
    while i < hi - 1:
        if payload[i] != 0xFF:
            i += 1
            continue
        modrm = payload[i + 1]
        mod, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
        if reg not in (2, 4) or mod == 3:
            i += 1
            continue
        p, base, ok = i + 2, None, True
        if rm == 4:
            sib = payload[p] if p < hi else 0
            p += 1
            bs = sib & 7
            base = None if (bs == 5 and mod == 0) else REGS[bs]
        elif rm == 5 and mod == 0:
            base = None
        else:
            base = REGS[rm]
        disp = 0
        if mod == 1:
            if p >= hi:
                break
            disp = payload[p]
            p += 1
        elif mod == 2 or base is None:
            if p + 4 > hi or p in relocs:
                ok = False
            else:
                disp = int.from_bytes(payload[p:p + 4], "little")
            p += 4
        if ok and base is not None and base not in frame \
                and disp % 4 == 0 and disp < MAX_SLOT:
            out.append((i - lo, "call" if reg == 2 else "jmp", base, disp))
        i = p
    return out


def _slots_obj(path: Path):
    obj = Obj(path)
    out, defined = {}, set()
    for secnum in range(1, obj.nsec + 1):
        if not (obj.section_table[secnum - 1]["characteristics"] & 0x20):
            continue
        payload = obj.section_payload(secnum)
        if not payload:
            continue
        rel = set(obj.typed_relocations(secnum))
        members = sorted((v, n) for v, n, _s in obj.section_members(secnum))
        defined.update(n for _v, n in members)
        offs = [v for v, _n in members]
        for i, (v, name) in enumerate(members):
            end = offs[i + 1] if i + 1 < len(offs) else len(payload)
            d = dispatches(payload, v, end, rel, frame_bases(payload, v))
            if d:
                out[name] = d
    return out, defined


#: `call DWORD PTR [reg+0x2c]` / `jmp DWORD PTR [reg]`, off a DECODED stream
DISPATCH = re.compile(r"^(call|jmp)\s+DWORD PTR \[(e[a-z]{2})"
                      r"(?:\+e[a-z]{2}\*\d)?(?:\+(0x[0-9a-f]+))?\]$")


def _decoded_slots(root: Path, side: str, unit: str, name: str):
    """The same reading off a real disassembly, for ADJUDICATING a row.

    The byte scan is right for a census and wrong for a verdict, because the
    two sides are not byte-symmetric: our base object has every `call rel32`
    displacement zeroed by its relocation, while the delinked target resolves
    a SELF-call internally and leaves a real negative displacement - four
    `ff` bytes that decode as `call DWORD PTR [edi+0xe8]`. `CRezArchiveDir`'s
    destructor is byte-identical to retail at 100.00 and still produced a
    retail-only slot 58 that way. So every differing row is re-read here.
    """
    from rom1.walls.diagnose import _find_function
    from rom1.walls.semdiff import _decode
    path = root / side / (f"{unit}.c.obj" if side == "target" else f"{unit}.obj")
    if side == "target" and not path.exists():
        path = root / side / f"{unit}.obj"
    body, rel, _size = _find_function(Obj(path), name)
    if body is None:
        return None
    frame = frame_bases(body, 0)
    out = Counter()
    for ln in _decode(body, rel, name):
        m = DISPATCH.match(ln.asm)
        if m and m.group(2) not in frame and not ln.ref:
            out[(m.group(1), int(m.group(3), 16) if m.group(3) else 0)] += 1
    return out


def slot_sweep(root: Path | None = None):
    root = root or NORM
    acc, defs = {}, {}
    for side in ("base", "target"):
        a, d = {}, {}
        for path in sorted((root / side).glob("*.obj")):
            unit = path.name.split(".")[0]
            st, dd = _slots_obj(path)
            d[unit] = dd
            for fn, v in st.items():
                a[(unit, fn)] = v
        acc[side], defs[side] = a, d
    both = {(u, n) for u, ns in defs["base"].items() for n in ns
            if n in defs["target"].get(u, ())}
    rows = []
    for k in sorted(both):
        o = Counter((s[1], s[3]) for s in acc["base"].get(k, ()))
        r = Counter((s[1], s[3]) for s in acc["target"].get(k, ()))
        if o == r:
            continue
        do = _decoded_slots(root, "base", *k)
        dr = _decoded_slots(root, "target", *k)
        if do is None or dr is None or do == dr:
            continue
        rows.append({"unit": k[0], "symbol": k[1], "ours": do, "retail": dr,
                     "same_count": sum(do.values()) == sum(dr.values()),
                     "ours_only": sorted(set(do) - set(dr)),
                     "retail_only": sorted(set(dr) - set(do))})
    return {"ours": acc["base"], "retail": acc["target"], "both": both,
            "rows": rows}


def slot_report(res, show_all: bool) -> None:
    both = res["both"]
    no = sum(len(v) for k, v in res["ours"].items() if k in both)
    nr = sum(len(v) for k, v in res["retail"].items() if k in both)
    hist = Counter(s[3] for k, v in res["ours"].items() if k in both
                   for s in v)
    print(f"indirect vtable dispatches : ours {no}, retail {nr}")
    print(f"  distinct slot displacements: {len(hist)}, deepest "
          f"+0x{max(hist):x} (slot {max(hist) // 4})")
    adjudicated = [r for r in res["rows"] if r["same_count"]]
    setdiff = [r for r in res["rows"] if not r["same_count"]
               and (r["ours_only"] or r["retail_only"])]
    print(f"rows whose slot multiset differs, re-read off a real disassembly "
          f": {len(res['rows'])}")
    print(f"  at the SAME COUNT - a slot MOVED : {len(adjudicated)}")
    print(f"  a slot one side never uses, inside a call-COUNT divergence: "
          f"{len(setdiff)}   (leads, not defects)")
    for r in adjudicated:
        print(f"\n  {r['unit']}/{r['symbol'][:60]}")
        print(f"    ours   {sorted(r['ours'].elements())}")
        print(f"    retail {sorted(r['retail'].elements())}")
    if show_all:
        for r in res["rows"]:
            if r["same_count"]:
                continue
            print(f"  {r['unit']}/{r['symbol'][:56]}")
            print(f"      ours   {sorted(r['ours'].elements())}")
            print(f"      retail {sorted(r['retail'].elements())}")


def _hermetic_slots() -> int:
    """A moved slot, and the three shapes a byte scan must not read as one."""
    mk = lambda hx: dispatches(bytes.fromhex(hx), 0, len(bytes.fromhex(hx)),
                               set(), {"esp"})
    bad = 0
    cases = [
        ("moved", "8b01ff502c", [0x2c],
         "POSITIVE: `mov eax,[ecx] / call DWORD PTR [eax+0x2c]` is slot 11; "
         "one byte says which virtual function runs"),
        ("register", "ffd0", [],
         "NEGATIVE: `call eax` has no slot"),
        ("odd", "ff5053", [],
         "NEGATIVE: `ff 50 53` decodes as `call [eax+0x53]`, and a slot is a "
         "pointer index - the multiple-of-4 bound is what removes the byte "
         "scan's misalignments"),
        ("absolute", "ff15aabbccdd", [],
         "NEGATIVE: `call DWORD PTR ds:0x...` is an import or a global, not a "
         "dispatch off an object"),
    ]
    for tag, hx, want, why in cases:
        got = [d[3] for d in mk(hx)]
        ok = got == want
        print(f"{'FIRES ' if got else 'SILENT'} slots-{tag:<9s} "
              f"{'ok' if ok else f'got {got}, want {want}'}")
        print(f"      {why}")
        bad += 0 if ok else 1
    return bad


def _hermetic() -> int:
    """The two defect kinds and their negatives, on synthesized bytes.

    A sieve nobody has seen FIRE is a green light, not a check - and this one
    reports ZERO over the whole image, so the positives are the only evidence
    that it reads anything at all. The bytes are a real stamp's:
    `mov DWORD PTR [esi+0x70],OFFSET ??_7CObject@@6B@`, which is
    `CDDrawWorkerHost`'s embedded CObject at +0x70.
    """
    def stamp(disp: int, ref: str):
        payload = bytearray(b"\x8b\xf1")              # mov esi,ecx
        if disp:
            payload += bytes((0xC7, 0x46, disp))      # mov [esi+d8],imm32
        else:
            payload += bytes((0xC7, 0x06))            # mov [esi],imm32
        site = len(payload)
        payload += b"\0\0\0\0"
        payload += b"\x8b\xc6\xc3"                    # mov eax,esi / ret
        return bytes(payload), {site: ref}

    def one(ours, retail):
        o, orel = ours
        r, rrel = retail
        mk = lambda p, rel: {("u", "f"): [
            (site - 0, decode_store(p, site)[2], decode_store(p, site)[0],
             name, False) for site, name in rel.items()]}
        return compare(mk(o, orel), mk(r, rrel), {("u", "f")})

    bad = 0
    cases = [
        ("offset", stamp(0x70, "??_7CObject@@6B@"),
         stamp(0x00, "??_7CObject@@6B@"), 1, 0,
         "POSITIVE: the vptr of an embedded CObject stamped into the wrong "
         "subobject - two bytes, and no other channel reads them"),
        ("vtable", stamp(0x70, "??_7CObject@@6B@"),
         stamp(0x70, "??_7CWwdGridIter@@6B@"), 0, 1,
         "POSITIVE: the right offset claiming the WRONG class, so every "
         "virtual call through it resolves to another class's slot"),
        ("clean", stamp(0x70, "??_7CObject@@6B@"),
         stamp(0x70, "??_7CObject@@6B@"), 0, 0,
         "NEGATIVE: the same stamp on both sides must be silent"),
    ]
    for tag, ours, retail, want_off, want_sym, why in cases:
        _rows, _n, off, sym = one(ours, retail)
        ok = (off, sym) == (want_off, want_sym)
        print(f"{'FIRES ' if (off or sym) else 'SILENT'} hermetic-{tag:<7s} "
              f"{'ok' if ok else f'got offset={off} vtable={sym}, want '
                                 f'offset={want_off} vtable={want_sym}'}")
        print(f"      {why}")
        bad += 0 if ok else 1
    return bad


def _stamp_site(obj: Obj):
    """(file offset of the imm32, file offset of the reloc RECORD, referent,
    a different vtable's symbol index) for one real non-frame stamp."""
    other = next((i for i, _v, _s in obj.iter_symbols()
                  if VTBL.match(obj.sym_name(i))), None)
    for secnum in range(1, obj.nsec + 1):
        sec = obj.section_table[secnum - 1]
        if not (sec["characteristics"] & 0x20) or not sec["reloc_offset"]:
            continue
        payload = obj.section_payload(secnum)
        raw = obj.sections[secnum - 1][0]
        for i in range(sec["reloc_count"]):
            rec = sec["reloc_offset"] + i * 10
            off = int.from_bytes(obj.buf[rec:rec + 4], "little")
            idx = int.from_bytes(obj.buf[rec + 4:rec + 8], "little")
            name = obj.sym_name(idx)
            dec = decode_store(payload, off)
            if dec and VTBL.match(name) and dec[2] and dec[0] != "esp":
                alt = next((j for j, _v, _s in obj.iter_symbols()
                            if VTBL.match(obj.sym_name(j))
                            and obj.sym_name(j) != name), other)
                return raw + off, rec, name, alt
    return None


def _injected(unit: str = "ddrawworkerhost") -> int:
    """The same two defects injected into a REAL object's bytes.

    The hermetic case proves the decoder; this proves the whole PATH - COFF
    parsing, the section-member table that attributes a site to its function,
    the relocation table, the pairing. One unit's own base object is copied
    twice: once with the stamp's displacement byte moved one subobject slot,
    once with the relocation RECORD re-pointed at another class's vtable. Each
    copy is swept against the untouched original.
    """
    import shutil
    import tempfile

    src = NORM / "base" / f"{unit}.obj"
    if not src.exists():
        print(f"SKIP   injected      {src} absent")
        return 0
    found = _stamp_site(Obj(src))
    if found is None:
        print(f"SKIP   injected      no non-frame vtable stamp in {unit}")
        return 0
    site, rec, ref, alt = found
    blob = src.read_bytes()

    def run(copy: bytes):
        with tempfile.TemporaryDirectory(prefix="rom1-vptrscan-") as tmp:
            root = Path(tmp)
            (root / "base").mkdir()
            (root / "target").mkdir()
            (root / "base" / f"{unit}.obj").write_bytes(copy)
            shutil.copy(src, root / "target" / f"{unit}.c.obj")
            res = sweep(root)
        return res["offset_defects"], res["vtable_defects"]

    moved = bytearray(blob)
    moved[site - 1] = (moved[site - 1] + 4) & 0xFF
    repointed = bytearray(blob)
    repointed[rec + 4:rec + 8] = alt.to_bytes(4, "little")

    bad = 0
    for tag, copy, want, why in (
            ("offset", bytes(moved), (1, 0),
             f"POSITIVE in real COFF: {unit}'s stamp of {ref} moved one "
             f"subobject slot - two bytes, read through the same parser, "
             f"member table and pairing the sweep uses"),
            ("vtable", bytes(repointed), (0, 1),
             "POSITIVE in real COFF: the relocation RECORD re-pointed at "
             "another class's vtable, so the object's dynamic type is wrong "
             "and every slot resolves elsewhere"),
            ("clean", blob, (0, 0),
             "NEGATIVE in real COFF: the object against ITSELF must be "
             "silent, which is what makes the two positives mean something")):
        got = run(copy)
        ok = got == want
        print(f"{'FIRES ' if any(got) else 'SILENT'} injected-{tag:<7s} "
              f"{'ok' if ok else f'got {got}, want {want}'}")
        print(f"      {why}")
        bad += 0 if ok else 1
    return bad


def control() -> int:
    """The hermetic pair, then the BACKWARDS run over the live image.

    Swapping the sides must leave the same verdict: the comparison is a
    symmetric statement about two byte streams, and a sieve that answers
    differently in one direction is reading its own asymmetry.
    """
    bad = _hermetic() + _injected() + _hermetic_slots()
    res = sweep()
    fwd = (res["offset_defects"], res["vtable_defects"])
    back = compare(res["retail"], res["ours"], res["both"])[2:]
    ok = fwd == back
    print(f"{'SILENT' if fwd == (0, 0) else 'FIRES '} live-forward   "
          f"offset={fwd[0]} vtable={fwd[1]}")
    print(f"{'SILENT' if back == (0, 0) else 'FIRES '} live-backwards "
          f"offset={back[0]} vtable={back[1]}  {'ok' if ok else 'ASYMMETRIC'}")
    print("      the sides swapped: a symmetric statement about two byte "
          "streams must give the same verdict either way")
    bad += 0 if ok else 1

    oh, _ = _counts(res["ours"], res["both"])
    nz = sum(1 for s in oh if s[1])
    sec = sum(1 for k in res["both"] for s in res["ours"].get(k, ())
              if SECONDARY.match(s[3]) and not s[4])
    split = nz >= 8 and sec >= 8 and len(oh) >= 200
    print(f"{'OK    ' if split else 'BROKEN'} live-split     "
          f"{len(oh)} stamps, {nz} at a non-zero offset, {sec} secondary-base")
    print("      a zero is only worth reading when the population it swept is "
          "non-trivial: the wrong-subobject question needs stamps that are "
          "NOT all at +0")
    bad += 0 if split else 1

    sl = slot_sweep()
    moved = [r for r in sl["rows"] if r["same_count"]]
    n = sum(len(v) for k, v in sl["ours"].items() if k in sl["both"])
    depth = {s[3] for k, v in sl["ours"].items() if k in sl["both"] for s in v}
    print(f"{'SILENT' if not moved else 'FIRES '} live-slots     "
          f"{len(moved)} slot(s) moved at the same call count, over {n} "
          f"dispatches in {len(depth)} distinct slots")
    print("      the companion reading: the stamp says the object claims the "
          "right class, the slot says the call reaches the right method of it")
    bad += 0 if (n >= 1000 and len(depth) >= 10) else 1
    if bad:
        print("\na control changed verdict: the image moved or the detector "
              "did - read it before trusting the sweep")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls vptrscan",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("--all", action="store_true",
                    help="also list the rows that differ only in stamp COUNT")
    ap.add_argument("--slots", action="store_true",
                    help="the companion reading: which vtable SLOT each "
                         "indirect dispatch calls")
    ap.add_argument("--control", action="store_true",
                    help="hermetic positives, negatives, and the backwards run")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.control:
        return control()
    if args.slots:
        slot_report(slot_sweep(), args.all)
        return 0
    res = sweep()
    if args.json:
        json.dump({"rows": res["rows"], "aligned": res["aligned"],
                   "offset_defects": res["offset_defects"],
                   "vtable_defects": res["vtable_defects"]}, sys.stdout)
        return 0
    report(res, args.all)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
