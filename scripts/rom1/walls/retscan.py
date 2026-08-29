"""rom1.walls.retscan - the one-sided calling-convention sieve.

    rom1 walls retscan [--all] [--blind] [--limit N] [--json]
    rom1 walls retscan --cdecl [--all]
    rom1 walls retscan --virtual [--limit N]

A callee's own `ret` states its convention and its stack-argument byte count,
in the retail image, with no compare report and no pairing: `ret` means the
CALLER cleans up (`__cdecl`), `ret N` means the callee pops N bytes of stack
arguments (`__stdcall` / `__thiscall`, the `this` in ECX never counted).  Our
declaration states the same two facts in its mangled name.  Disagreement is a
signature defect - a dropped or an added argument, or the wrong convention -
and it is decided by retail's bytes alone.

This is the ADJACENT class to `walls thisscan`, not the same one.  A dropped
RECEIVER is invisible here by construction: the receiver rides in ECX and is
not part of `ret N`, which is why `CBattlezMapConfig::TileSwitch` - a member
modelled as a free `__stdcall` - passed this screen at every stage while it
was wrong.  Read the two together: thisscan owns ECX, retscan owns the stack.

WHOLE-IMAGE CENSUS, 2026-08-23.  Both populations, and both are CLEAN:

                                    `src` (our own)   config/retail labels
    decidable (a singleton `ret`)          3905               1764
    UDT-bounded (inequality, below)          57                 27
    agree                                  3962               1791
    DISAGREE                                  0                  0
    blind: no `ret` reachable at all         15                 20

  recovered rather than parked, and counted so the census is a SET:
    tail `jmp` followed to the callee's `ret`  30                26
    more than one `ret` immediate in extent     7                53
    linear sweep desynced, re-decoded alone    13                 7

The UDT rows keep an INEQUALITY test rather than being dropped: a by-value
UDT parameter occupies at least one 4-byte slot, so a `ret N` below (known
bytes + 4 per UDT) is a defect whatever the class sizes are.  The 15 `src`
blind rows are all the same shape - a body whose only exit is an INDIRECT
tail jump (`jmp DWORD PTR [eax+0x40]`, a virtual dispatch), which states no
immediate at all.

FIVE ABI RULES, each of which the census discovered by producing a uniform
false hit before it existed.  They are the content of this tool:

  1. `this` is NOT in `ret N` for `__thiscall` - it rides in ECX.  That is
     why a dropped RECEIVER is invisible here (see thisscan).
  2. `this` IS in `ret N` for a non-static member declared `__stdcall` -
     every COM `STDMETHOD`.  `CArchiveStream`'s seven IStream methods read as
     a uniform +4 without this.
  3. A constructor of a class with a VIRTUAL BASE carries cl's hidden
     most-derived flag, which the mangling does not record.  Eleven iostream
     constructors (`ifstream`, `ofstream`, `istream`, `strstream`, all
     virtually derived from `ios`) read as a uniform +4 without it, so a
     constructor's expectation is WIDENED to {N, N+4} rather than decided.
  4. A by-value UDT return may or may not use a caller-supplied hidden
     pointer - cl returns a small POD in EAX:EDX - so that widens too.
  5. MSVC mangles a NAMESPACE scope exactly like a class scope, so `::` in a
     demangled spelling does not mean "member".  `NetLobby::HostWaitDlgProc`
     and its five siblings are free `@@YG` dialog procs and read as a uniform
     -4 under a `::` test; the ACCESS SPECIFIER is what says member.

The CONTROL is the exact rows.  A function scoring 100.00 is byte-identical
to retail, so ITS `ret` is retail's `ret` and a flagged row can only be a
parser bug.  The cell is 0, and it earned its keep: it caught all four
defects of the first run, all of them mine.  Two were parameter-list parses
(a template argument that is itself a function type puts parentheses in the
CLASS name; a function RETURNING a function pointer puts its own parameters
in the middle of the spelling), and rule 5 above was the other two.

The library labels are the second population and a different question: a
mismatch there is a wrong CLAIM in config/retail (a FLIRT collision), not a
reconstruction defect.  `--all` runs them.  It is also where the `ret`
MEMBERSHIP rule was forced: `__ArrayUnwind` has a `/GX` funclet cl emits
INSIDE the parent's extent, whose bare `ret` decodes BEFORE the function's
own `ret 0x10`, while a switch table decodes spurious `ret`s AFTER it.  No
position rule survives both, so a row agrees when the expected value is
PRESENT among the immediates decoded - a spurious decode can add a value but
never remove the true one.  That trades recall on the 60 non-singleton rows
for freedom from false positives.

`--cdecl` IS THE HALF `ret 0` CANNOT DO.  For a `__cdecl` callee `ret` states
the convention and NOTHING about the arity - the callee pops nothing, so a
trailing argument it never reads is invisible in its own bytes exactly as a
receiver is.  The caller's `add esp,N` is the only witness, and reading it
from RETAIL alone keeps the screen one-sided: it needs no reconstructed,
paired or scoring caller, which is what separates it from
`walls thisscan --arity`.

Four reader rules, each forced by a false hit:

  * ONE `add esp,N` is the whole cleanup.  A SECOND is the caller releasing
    its own storage - `call DiscardDebugOutput / add esp,0x4 / add esp,0x100`
    reads as popping 0x104 if the two are summed.
  * cl 5.0 spells a two-argument cleanup as two `pop ecx` AND is free to put
    an instruction between them (`pop ecx / test eax,eax / pop ecx`), so the
    run accumulates across non-esp instructions.  Five MFC rows
    (`DestructElements`, `ConstructElements`, `FindPopupMenuFromID`,
    `AfxDynamicDownCast`, `AfxTimeToFileTime`) read as popping 4 of 8 when it
    was cut at the first one.
  * `pop esi` / `pop edi` / `pop ebp` is the EPILOGUE, never an argument.
    Walking past them reaches the caller's frame release -
    `BuildColorChannelTables()` takes nothing and its caller's `add esp,0x6c`
    sits three instructions later.
  * a zero-argument callee has nothing to check, and any nearby `add esp` is
    the caller's business, so those rows are skipped rather than screened.

The cleanup may legitimately sit one or two instructions after the call
(`call MakeButeSectionKey / mov eax,[esi+0x5a4] / add esp,0xc`), so the
window is four; a site whose cleanup cl merged with a neighbour's shows up as
sites disagreeing and is parked.

2026-08-23: 130 of our `__cdecl` declarations and 36 config/retail labels
decidable, ZERO disagreements.  Blind: 107 with no direct retail call site,
87 with no arguments, 7 varargs (a vararg site's cleanup is its own).

`--virtual` is the vtable-slot census, kept here because it asks the same
one-sided question of the same names.  Its FORWARD direction - a body a
retail vtable slot holds, declared non-virtual - is ALREADY a fail-closed
gate (`rom1 verify vtables`, SLOT BINDING: WIRING is FATAL), and this
independent re-derivation agrees with it: 0 game-side rows.  Two artifacts
are worth stating because both cost a false hit on the way:

  * a slot is resolved through a `jmp` only when the jmp's address carries no
    named body of its own.  `CDDrawSubMgrLeaf::Unload` is a real five-byte
    body that cl tail-jumps into `FreeAll`; resolving through it accuses
    `FreeAll` of being an undeclared virtual.
  * virtualness is read from llvm-undname's `virtual` keyword, never from the
    access code after `@@` in the mangling - a template argument carries its
    own `@@` (`??_G?$zDArray@P8CUserLogic@@AEHXZ@@UAEPAXI@Z` reads as `A`).

The INVERSE direction measures RECALL, not noise, and is reported as such: a
`virtual ~C()` is never in a slot because the slot holds cl's `??_G` vector
deleting destructor, which CALLS it - 77 of the 78 `src` rows are that, and
the single remainder (`CPreviewState::OnLButtonDown`, 0xde400) is undecidable
rather than wrong: retail holds no `??_7CPreviewState@@6B@`, our own objects
emit none either, and nothing in the image references the body or its ILT
forwarder, so no vtable of either side can witness the question.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter

from rom1.model import resolve
from rom1.sema.image import retail
from rom1.tool import objdump

#: the convention keywords llvm-undname spells
CONV = re.compile(r"__(cdecl|stdcall|thiscall|fastcall)\b")
RET = re.compile(r"^ret\s*(0x[0-9a-f]+)?$")
#: a scalar that occupies one 4-byte stack slot
SCALAR4 = re.compile(
    r"^(?:(?:signed |unsigned )?(?:char|short|int|long|__int32)|float|bool"
    r"|wchar_t|void)$")
WIDE8 = re.compile(r"^(?:double|long double|(?:unsigned )?__int64)$")
#: `void (__cdecl *)(int)` - a plain function pointer, one slot.  A POINTER TO
#: MEMBER FUNCTION (`int (__thiscall C::*)(void)`) is NOT: its size is 4, 8 or
#: 12 by the inheritance model, so it stays a blind spot.
FNPTR = re.compile(r"\(\s*__(?:cdecl|stdcall|thiscall|fastcall)\s*\*\s*\)")
MEMPTR = re.compile(r"::\s*\*")


def demangle(names: list[str]) -> dict[str, str]:
    """{mangled: llvm-undname's spelling} - one process for the whole list.

    Two harness facts, both measured: llvm-undname DROPS a final line with no
    trailing newline (which silently cost `?EnsureSize@zBitVec@@QAEHH@Z`, the
    last name of the corpus, its row), and it separates records with a blank
    line - so the records are split on that rather than paired by "a line
    starting with `?` is a name", which desyncs on any spelling that does.
    """
    proc = subprocess.run(["llvm-undname"], input="\n".join(names) + "\n",
                          capture_output=True, text=True)
    out: dict[str, str] = {}
    for block in proc.stdout.split("\n\n"):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) >= 2:
            out[lines[0]] = " ".join(lines[1:])
    return out


def declarator(sig: str) -> int | None:
    """Index of the DECLARATOR's convention keyword in a demangled signature.

    A function returning a function pointer is spelled
    `RET (__cdecl * __thiscall C::Add(PARAMS))(RETPARAMS)`, so the first
    convention keyword belongs to the RETURN type.  The declarator's is the
    one followed by a name rather than by `*` or `(`.
    """
    for m in CONV.finditer(sig):
        j = m.end()
        while j < len(sig) and sig[j] == " ":
            j += 1
        if j < len(sig) and sig[j] not in "*(":
            return m.start()
    return None


#: `operator<<` puts unbalanced angle brackets in a NAME. Blanked to keep the
#: template-argument scan below honest, same length so offsets are unchanged.
OPERATOR = re.compile(r"operator(<<|>>|<=|>=|<|>)")


def params(sig: str) -> str | None:
    """The declarator's own parameter-list text."""
    start = declarator(sig)
    if start is None:
        return None
    sig = OPERATOR.sub(lambda m: "operator" + "_" * len(m.group(1)), sig)
    j = start + 1
    ang = 0
    while j < len(sig):                      # skip the qualified name, whose
        c = sig[j]                           # template arguments hold parens
        if c == "<":
            ang += 1
        elif c == ">":
            ang -= 1
        elif c == "(" and ang == 0:
            break
        j += 1
    else:
        return None
    depth, first = 0, j + 1
    while j < len(sig):
        if sig[j] == "(":
            depth += 1
        elif sig[j] == ")":
            depth -= 1
            if depth == 0:
                return sig[first:j]
        j += 1
    return None


def split_top(text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def stack_bytes(sig: str) -> tuple[int, int, str]:
    """(known bytes, by-value UDT count, blind-spot reason).

    The UDT count is what keeps an unmeasurable row usable: each occupies at
    least one 4-byte slot, so `known + 4*udt` is a hard lower bound on `ret N`.
    """
    text = params(sig)
    if text is None:
        return 0, 0, "no-params"
    text = text.strip()
    if text in ("void", ""):
        return 0, 0, ""
    known, udt, why = 0, 0, ""
    for p in split_top(text):
        if p == "...":
            return known, udt, "varargs"
        if p.endswith("*") or p.endswith("&") or FNPTR.search(p):
            known += 4
            continue
        if MEMPTR.search(p):
            udt += 1                      # 4, 8 or 12 by inheritance model
            why = "member-pointer"
            continue
        base = re.sub(r"^(?:class|struct|union|enum) ", "", p)
        base = re.sub(r"\bconst\b|\bvolatile\b", "", base).strip()
        if p.startswith("enum "):
            known += 4
        elif WIDE8.match(base):
            known += 8
        elif SCALAR4.match(base):
            known += 4
        else:
            udt += 1
            why = "udt-param"
    return known, udt, why


def receiver_on_stack(sig: str) -> bool:
    """Whether the callee also pops a `this` it was handed on the STACK.

    `__thiscall` keeps the receiver in ECX, which `ret N` never counts - but a
    non-static member declared `__stdcall` (every `STDMETHOD` of a COM
    interface: `CArchiveStream::Read` and its six siblings) takes `this` as an
    ordinary stack argument and pops it with the rest.  All seven read as a
    uniform +4 before this rule existed.
    """
    start = declarator(sig)
    if start is None or CONV.search(sig, start).group(1) != "stdcall":
        return False
    m = re.match(r"(?:public|protected|private): (static )?", sig)
    # MSVC mangles a NAMESPACE scope exactly like a class scope, so `::` in
    # the spelling proves nothing: `NetLobby::HostWaitDlgProc` and its five
    # siblings are free `@@YG` dialog procs and read as a uniform -4 under a
    # `::` test.  The access specifier is what says "member".
    return bool(m) and not m.group(1)


def vbase_ctor_flag(name: str) -> bool:
    """Whether a constructor may carry cl's hidden most-derived flag.

    A class with a VIRTUAL base gets an extra int argument in every
    constructor, and the mangling does not record it.  Eleven iostream
    constructors (`ifstream`, `ofstream`, `istream`, `strstream`, ... all
    virtually derived from `ios`) read as a uniform +4 on that alone, so a
    constructor's expectation is widened rather than decided.
    """
    return name.startswith("??0")


def hidden_return_pointer(sig: str) -> bool:
    """Whether the return value MAY travel through a caller-supplied pointer.

    cl returns a small POD in EAX:EDX and anything with a constructor through
    a hidden pointer that the callee pops, and the mangling does not say
    which - so a by-value UDT return widens the expectation by 4 rather than
    deciding it.
    """
    start = declarator(sig)
    if start is None:
        return False
    head = sig[:start]
    head = re.sub(r"^(?:public|protected|private):\s*", "", head).strip()
    head = re.sub(r"^(?:static|virtual)\s+", "", head).strip()
    head = re.sub(r"^(?:static|virtual)\s+", "", head).strip()
    if head.endswith(("*", "&")) or "(" in head:
        return False
    return head.startswith(("class ", "struct ", "union "))


def text_lines(img) -> dict[int, str]:
    """{address: instruction} for one linear sweep of the whole .text."""
    sec = next(s for s in img.pe.sections if s["name"] == ".text")
    blob = img.read(sec["va"], sec["vsize"])
    out: dict[int, str] = {}
    for line in objdump.disassemble(blob, vma=sec["va"]).splitlines():
        if ":\t" not in line:
            continue
        head, rest = line.split(":\t", 1)
        try:
            addr = int(head.strip(), 16)
        except ValueError:
            continue
        parts = rest.split("\t")
        out[addr] = " ".join((parts[-1] if len(parts) > 1 else parts[0]).split())
    return out


def body_rets(img, rva: int, size: int) -> list[int] | None:
    """`ret` immediates in one function, decoded from its own start."""
    blob = img.read(rva, size)
    if not blob:
        return None
    out = []
    for line in objdump.disassemble(blob, vma=rva).splitlines():
        if ":\t" not in line:
            continue
        parts = line.split(":\t", 1)[1].split("\t")
        asm = " ".join((parts[-1] if len(parts) > 1 else parts[0]).split())
        m = RET.match(asm)
        if m:
            out.append(int(m.group(1), 16) if m.group(1) else 0)
    return out


def rets_in(img, tmap, rva: int, size: int) -> tuple[list[int] | None, bool]:
    """(`ret` immediates, whether the whole-.text sweep had to be re-run).

    The sweep is only trustworthy where it starts an instruction exactly at
    the function's rva; otherwise the function is decoded on its own.
    """
    if rva in tmap:
        out = [int(m.group(1), 16) if m.group(1) else 0
               for k in range(rva, rva + size)
               if k in tmap and (m := RET.match(tmap[k]))]
        return out, False
    return body_rets(img, rva, size), True


TAILJMP = re.compile(r"^jmp\s+0x([0-9a-f]+)$")


def tail_ret(img, idx, tmap, rva: int, size: int, depth: int = 3):
    """The `ret` of the body a `ret`-less function tail-jumps into.

    cl 5.0 turns `void Unload() { FreeAll(); }` into a bare five-byte
    `jmp FreeAll`, so the extent holds no `ret` at all.  A tail jump is only
    legal between functions with the SAME stack-argument bytes, which makes
    the target's `ret` the caller's `ret` - that is what recovers 34 of the
    45 `ret`-less rows instead of parking them.
    """
    if depth <= 0:
        return None
    keys = sorted(k for k in tmap if rva <= k < rva + size) if rva in tmap else []
    asm = tmap[keys[-1]] if keys else None
    if asm is None:
        blob = img.read(rva, size)
        lines = objdump.disassemble(blob, vma=rva).splitlines() if blob else []
        for line in reversed(lines):
            if ":\t" in line:
                parts = line.split(":\t", 1)[1].split("\t")
                asm = " ".join(
                    (parts[-1] if len(parts) > 1 else parts[0]).split())
                break
    m = TAILJMP.match(asm or "")
    if m is None:
        return None
    tgt = int(m.group(1), 16)
    tgt = img.jmp_target(tgt) or tgt
    b = idx.func(tgt)
    if b is None or not b.size or b.rva == rva:
        return None
    rs, _ = rets_in(img, tmap, b.rva, b.size)
    if rs:
        return Counter(rs).most_common(1)[0][0]
    return tail_ret(img, idx, tmap, b.rva, b.size, depth - 1)


def scan(bindings, scores, recall: list | None = None
         ) -> tuple[list[dict], Counter, list[dict]]:
    from rom1.sema.index import index
    img = retail()
    idx = index()
    tmap = text_lines(img)
    dm = demangle([b.name for b in bindings])
    stat, rows, blind = Counter(), [], []

    def skip(b, why, sig=""):
        stat["blind:" + why] += 1
        blind.append({"rva": b.rva, "unit": b.unit or "", "why": why,
                      "name": b.name, "sig": sig})

    for b in bindings:
        sig = dm.get(b.name)
        if not sig:
            skip(b, "no-demangle")
            continue
        start = declarator(sig)
        if start is None:
            skip(b, "no-convention", sig)
            continue
        conv = CONV.search(sig, start).group(1)
        rs, resweep = rets_in(img, tmap, b.rva, b.size)
        if rs is None:
            skip(b, "unreadable", sig)
            continue
        if resweep:
            stat["resweep"] += 1
        if not rs:
            tail = tail_ret(img, idx, tmap, b.rva, b.size)
            if tail is None:
                skip(b, "no-ret", sig)
                continue
            stat["tail-jmp"] += 1
            seen = {tail}
        else:
            # An extent can decode MORE than one `ret` immediate for two
            # reasons, and neither position rule survives both: a linear sweep
            # through an embedded switch table invents `ret`s AFTER the real
            # one (`CButeMgr::SetString` reads 0xc then 0x5733 twice), while a
            # `/GX` funclet cl emits INSIDE the parent's extent contributes a
            # real `ret` BEFORE it (`__ArrayUnwind` reads the funclet's bare
            # `ret` at +0x4c and its own `ret 0x10` at +0x67).  So the test is
            # MEMBERSHIP: a spurious decode can add a value but never remove
            # the true one, which keeps the screen free of false positives at
            # the cost of recall on the 60 rows that are not a singleton.
            seen = set(rs)
            if len(seen) != 1:
                stat["multi-ret"] += 1
        actual = min(seen)
        known, udt, why = stack_bytes(sig)
        if why == "no-params":
            skip(b, "no-params", sig)
            continue
        if receiver_on_stack(sig):
            known += 4
        if conv == "cdecl":
            expect, lower = {0}, 0
        elif conv == "fastcall":
            # ECX and EDX carry the first two register-eligible arguments; the
            # rest stay on the stack and the callee pops them.
            reg = min(2, len(split_top(params(sig) or "")))
            expect, lower = {max(0, known - 4 * reg)}, 0
            if udt:
                expect, lower = set(), 0
        else:
            expect = {known} if not udt else set()
            if hidden_return_pointer(sig) or vbase_ctor_flag(b.name):
                expect |= {v + 4 for v in expect}
            lower = known + 4 * udt
        bad = (all(v < lower for v in seen) if udt
               else not (seen & expect))
        stat["udt-bounded" if udt else "decidable"] += 1
        if not bad:
            stat["agree"] += 1
            # THE MEMBERSHIP RULE'S COST, which the exact-row control cannot
            # measure: an exact row cannot exhibit a MISSED disagreement, so
            # that control bounds false POSITIVES only. Where more than one
            # `ret` immediate decoded, ask whether the row would still agree
            # under the strict single-value reading (the most common one).
            if recall is not None and len(seen) > 1:
                primary = Counter(rs).most_common(1)[0][0] if rs else None
                if (primary < lower) if udt else (primary not in expect):
                    recall.append({"rva": b.rva, "unit": b.unit or "",
                                   "name": b.name, "sig": sig, "conv": conv,
                                   "seen": sorted(seen), "primary": primary,
                                   "expect": sorted(expect), "lower": lower,
                                   "cur": scores.get((b.unit, b.name))})
            continue
        stat["DISAGREE"] += 1
        rows.append({"rva": b.rva, "unit": b.unit or "", "name": b.name,
                     "sig": sig, "conv": conv,
                     "actual": sorted(seen), "expect": sorted(expect),
                     "lower": lower, "udt": udt, "note": why,
                     "cur": scores.get((b.unit, b.name))})
    return rows, stat, blind


def report(title, rows, stat, limit, scores):
    print(f"\n{title}")
    for k in ("decidable", "udt-bounded", "agree", "DISAGREE",
              "tail-jmp", "multi-ret", "resweep"):
        if k in stat:
            print(f"    {k:24} {stat[k]:5d}")
    for k in sorted(stat):
        if k.startswith("blind:"):
            print(f"    {k:24} {stat[k]:5d}")
    exact = [r for r in rows if r["cur"] is not None and r["cur"] >= 100.0]
    print(f"    control (rows at 100.00, which cannot disagree): "
          f"{len(exact)}   <- must be 0")
    for r in rows[:limit]:
        want = (f"expect ret {'/'.join(f'0x{v:x}' for v in r['expect'])}"
                if r["expect"] else f"expect ret >= 0x{r['lower']:x}")
        cur = "n/a" if r["cur"] is None else f"{r['cur']:.2f}"
        got = "/".join(f"0x{v:x}" for v in r["actual"])
        print(f"  0x{r['rva']:08x} {r['unit'][:20]:20} cur {cur:>6}  "
              f"{r['conv']:8} {want}, retail ret {got}"
              + (f"  [{r['note']}]" if r["note"] else ""))
        print(f"      {r['sig'][:150]}")


#: the caller-side cleanup of a `__cdecl` call. cl 5.0 spells `add esp,4` as
#: `pop ecx`, and merges the cleanup of adjacent calls into one `add`.
CLEANUP = re.compile(r"^add\s+esp,(0x[0-9a-f]+)$")
CALL_AT = re.compile(r"^call\s+0x[0-9a-f]+$")
#: the cleanup run ends here: a transfer, the next call's arguments, or a
#: callee-saved restore. `pop esi`/`pop edi`/`pop ebp` is the EPILOGUE - only
#: `pop ecx` is cl's spelling of `add esp,4`, and walking past the others
#: reaches the caller's own frame release (`BuildColorChannelTables()` takes
#: nothing and its caller's `add esp,0x6c` sits three instructions later).
CLEANUP_STOP = re.compile(
    r"^(call|jmp|j\w+|ret|leave|push|int3|nop|pop\s+(?!ecx))\b")
#: how far past the call a cleanup may sit. Three of the five first-run
#: false hits had one instruction between the call and its `add esp,N`
#: (`call MakeButeSectionKey / mov eax,[esi+0x5a4] / add esp,0xc`).
CLEANUP_WINDOW = 4


def cdecl_cleanups(img, tmap, rva: int):
    """[(site, bytes the CALLER pops)] over retail's direct calls to `rva`.

    A `__cdecl` callee pops nothing, so `ret` says its convention and NOTHING
    about its arity: a trailing argument it never reads is invisible in its
    own bytes exactly as a receiver is. The caller's `add esp,N` is the only
    witness, and reading it from RETAIL alone keeps the screen one-sided -
    it does not need the caller reconstructed, paired, or scoring.
    """
    entries = [rva] + img.thunks_to(rva)
    sites = sorted({s for e in entries
                    for s, op in img.call_index.get(e, ()) if op == 0xE8})
    keys = None
    out = []
    for site in sites:
        if site not in tmap or not CALL_AT.match(tmap[site]):
            continue                    # the 0xE8 scan hit an immediate, or
        if keys is None:                # the sweep is not synced here
            keys = sorted(tmap)
        i = __import__("bisect").bisect_right(keys, site)
        popped = 0
        for k in keys[i:i + CLEANUP_WINDOW]:
            asm = tmap[k]
            if CLEANUP_STOP.match(asm):
                break
            m = CLEANUP.match(asm)
            if m:
                # ONE `add esp,N` is the whole cleanup. A SECOND one is the
                # caller releasing its own storage, not more arguments:
                # `call DiscardDebugOutput / add esp,0x4 / add esp,0x100`
                # reads as popping 0x104 if the two are summed.
                popped += int(m.group(1), 16)
                break
            if asm == "pop ecx":
                # cl 5.0 spells a two-argument cleanup as two `pop ecx`, and
                # is free to put an instruction BETWEEN them
                # (`pop ecx / test eax,eax / pop ecx`), so the run is
                # accumulated across non-esp instructions rather than cut at
                # the first one. Five MFC rows read as popping 4 of 8 when it
                # was cut.
                popped += 4
        if popped:
            out.append((site, popped))
    return out, len(sites)


def cdecl_screen(bindings, limit: int, as_json: bool, label: str) -> list[dict]:
    """Our declared `__cdecl` argument bytes against retail's caller cleanup."""
    from rom1.sema.index import index
    img = retail()
    idx = index()
    tmap = text_lines(img)
    dm = demangle([b.name for b in bindings])
    stat, rows = Counter(), []
    for b in bindings:
        sig = dm.get(b.name)
        if not sig:
            continue
        start = declarator(sig)
        if start is None or CONV.search(sig, start).group(1) != "cdecl":
            continue
        stat["cdecl"] += 1
        known, udt, why = stack_bytes(sig)
        if why in ("no-params", "varargs"):
            stat["blind:" + why] += 1     # a vararg site's cleanup is its own
            continue
        if not known and not udt:
            # nothing to check: a zero-argument `__cdecl` call needs no
            # cleanup, so any nearby `add esp` belongs to the caller
            stat["blind:no-arguments"] += 1
            continue
        cleanups, nsites = cdecl_cleanups(img, tmap, b.rva)
        if not nsites:
            stat["blind:no-call-site"] += 1
            continue
        if not cleanups:
            stat["blind:no-adjacent-cleanup"] += 1
            continue
        seen = {c for _s, c in cleanups}
        if len(seen) != 1:
            # cl merges the cleanup of ADJACENT calls into one `add esp,N`,
            # so a site can legitimately pop more than its own arguments.
            stat["blind:merged-cleanup"] += 1
            continue
        actual = seen.pop()
        expect = {known}
        if hidden_return_pointer(sig):
            expect.add(known + 4)         # the caller pops the hidden pointer
        lower = known + 4 * udt
        bad = (actual < lower) if udt else (actual not in expect)
        stat["udt-bounded" if udt else "decidable"] += 1
        if not bad:
            stat["agree"] += 1
            continue
        stat["DISAGREE"] += 1
        rows.append({"rva": b.rva, "unit": b.unit or "", "name": b.name,
                     "sig": sig, "expect": sorted(expect), "lower": lower,
                     "udt": udt, "actual": actual, "sites": len(cleanups),
                     "all_sites": nsites})
    if as_json:
        return rows
    print(f"\n{label}")
    for k in ("cdecl", "decidable", "udt-bounded", "agree", "DISAGREE"):
        if k in stat:
            print(f"    {k:24} {stat[k]:5d}")
    for k in sorted(stat):
        if k.startswith("blind:"):
            print(f"    {k:24} {stat[k]:5d}")
    for r in rows[:limit]:
        want = (f"expect esp+{'/'.join(f'0x{v:x}' for v in r['expect'])}"
                if r["expect"] and not r["udt"]
                else f"expect esp+>=0x{r['lower']:x}")
        print(f"  0x{r['rva']:08x} {r['unit'][:20]:20} {want}, retail pops "
              f"0x{r['actual']:x} at {r['sites']}/{r['all_sites']} site(s)")
        print(f"      {r['sig'][:150]}")
    return rows


def report_blind(blind, limit: int) -> None:
    """The rows the screen could not decide, so the census is a SET rather
    than a percentage. Read them by hand: they are where a defect hides."""
    per = Counter(r["why"] for r in blind)
    print("\n  blind spots, by reason:")
    for why, n in per.most_common():
        print(f"    {why:16} {n:4d}")
        for r in [x for x in blind if x["why"] == why][:limit]:
            print(f"      0x{r['rva']:08x} {r['unit'][:20]:20} "
                  f"{(r['sig'] or r['name'])[:96]}")


def virtual_census(limit: int) -> int:
    from rom1.sema.index import index
    from rom1.sema.vtable import slots, vtable_rows
    idx = index()
    occupied, holder = set(), {}
    for b in vtable_rows():
        for k, tgt, body in slots(b):
            row = idx.func(tgt)
            real = tgt
            if body is not None and body != tgt and (
                    row is None or row.kind == "thunk" or not row.name):
                real = body
            occupied.add(real)
            holder.setdefault(real, (b.name or f"@0x{b.rva:06x}", k))
    named = [f for f in resolve().functions if f.name and f.name.startswith("?")]
    dm = demangle([f.name for f in named])
    stat, fwd, inv = Counter(), [], []
    for f in named:
        sig = dm.get(f.name)
        if not sig:
            continue
        if sig.startswith("[thunk]"):
            stat["adjustor-thunk"] += 1
            continue
        virt = re.match(r"(?:public|protected|private): virtual\b|^virtual\b",
                        sig) is not None
        if virt:
            stat["declared-virtual"] += 1
            if f.rva not in occupied:
                dtor = "::~" in sig
                stat[f"no-slot:{'destructor' if dtor else 'method'}:"
                     f"{f.channel or '-'}"] += 1
                if not dtor:
                    inv.append((f, sig))
        elif f.rva in occupied:
            stat[f"IN-SLOT-NOT-VIRTUAL:{f.channel or '-'}"] += 1
            fwd.append((f, sig))
    for k, v in sorted(stat.items()):
        print(f"  {k:44} {v}")
    print("\nFORWARD - a body a retail vtable slot holds, declared "
          "non-virtual\n  (`rom1 verify vtables` already gates this "
          "fail-closed; this is the control):")
    for f, sig in fwd[:limit]:
        print(f"  0x{f.rva:08x} [{f.channel or '-':22}] "
              f"slot {holder.get(f.rva)}  {sig[:88]}")
    print("\nINVERSE - declared virtual, no retail slot.  This measures "
          "RECALL: a\n  `virtual ~C()` is never in a slot (the slot holds "
          "cl's `??_G`, which calls it),\n  and a class whose vtable neither "
          "side emits cannot be decided at all.")
    for f, sig in inv[:limit]:
        print(f"  0x{f.rva:08x} [{f.channel or '-':16}] {f.unit or '-':22} "
              f"{sig[:88]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="rom1 walls retscan",
        description=__doc__.split("\n\n")[0])
    ap.add_argument("--all", action="store_true",
                    help="also run the config/retail library labels, where a "
                         "mismatch is a wrong CLAIM rather than a defect")
    ap.add_argument("--blind", action="store_true",
                    help="list the rows the screen cannot decide, by reason")
    ap.add_argument("--cdecl", action="store_true",
                    help="the arity screen `ret 0` cannot do: our declared "
                         "__cdecl argument bytes against RETAIL's caller "
                         "cleanup (`add esp,N`), read one-sided")
    ap.add_argument("--virtual", action="store_true",
                    help="the vtable-slot census over the same names")
    ap.add_argument("--recall", action="store_true",
                    help="the MEMBERSHIP rule's cost - agreeing rows that "
                         "would disagree under the strict single-`ret` "
                         "reading. The exact-row control cannot see this: an "
                         "exact row cannot exhibit a MISSED disagreement")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.virtual:
        return virtual_census(args.limit)

    from rom1.walls.inventory import report_scores
    try:
        _path, scores = report_scores()
    except SystemExit:
        scores = {}
    model = resolve()
    named = [b for b in model.functions
             if b.name and b.name.startswith("?") and b.size]
    ours = [b for b in named if b.channel == "src"]
    if args.cdecl:
        out = {"src": cdecl_screen(
            ours, args.limit, args.json,
            "OUR `__cdecl` DECLARATIONS - `ret 0` states the convention and "
            "nothing\nabout the arity, so the witness is retail's own caller "
            "cleanup:")}
        if args.all:
            out["other"] = cdecl_screen(
                [b for b in named if b.channel != "src"], args.limit,
                args.json, "EVERY OTHER `__cdecl` CLAIM (library labels):")
        if args.json:
            json.dump(out, sys.stdout)
        return 0
    if args.recall:
        pops = [("OUR DECLARATIONS (channel `src`)", ours)]
        if args.all:
            pops.append(("EVERY OTHER CLAIM (library labels)",
                         [b for b in named if b.channel != "src"]))
        for title, pop in pops:
            got: list[dict] = []
            _r, st, _b = scan(pop, scores, got)
            print(f"\n{title}")
            print(f"  rows decided                       "
                  f"{st['decidable'] + st['udt-bounded']:5d}")
            print(f"  ... more than one `ret` immediate  {st['multi-ret']:5d}"
                  "   <- the only rows the rule can hide anything in")
            print(f"  ... AGREEING only on a non-primary "
                  f"immediate {len(got):5d}   <- the recall cost")
            for r in got[:args.limit]:
                want = ("/".join(f"0x{v:x}" for v in r["expect"])
                        if r["expect"] else f">= 0x{r['lower']:x}")
                print(f"  0x{r['rva']:08x} {r['unit'][:20]:20} {r['conv']:8} "
                      f"expect {want}, decoded "
                      f"{'/'.join(f'0x{v:x}' for v in r['seen'])}, "
                      f"primary 0x{r['primary']:x}")
                print(f"      {r['sig'][:150]}")
        return 0

    rows, stat, blind = scan(ours, scores)
    out = {"src": {"stat": dict(stat), "rows": rows, "blind": blind}}
    if not args.json:
        report("OUR DECLARATIONS (channel `src`) - retail `ret` against the "
               "mangled\nname's stack-argument bytes:", rows, stat,
               args.limit, scores)
        if args.blind:
            report_blind(blind, args.limit)
    if args.all:
        lib = [b for b in named if b.channel != "src"]
        lrows, lstat, lblind = scan(lib, scores)
        out["other"] = {"stat": dict(lstat), "rows": lrows, "blind": lblind}
        if not args.json:
            report("EVERY OTHER CLAIM (library labels, compiler-generated) - "
                   "a mismatch\nhere is a wrong claim in config/retail, not a "
                   "reconstruction defect:", lrows, lstat, args.limit, scores)
            if args.blind:
                report_blind(lblind, args.limit)
    if args.json:
        json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
