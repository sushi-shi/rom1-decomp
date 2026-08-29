"""rom1.walls.residue - NAME the masked residual of every paired wall.

`walls framescan` proved the frame-size vein is drained and left ~500 rows
whose frame already EQUALS retail's. This sieve says what is left in each of
them, by reducing the diff twice before it classifies:

    1. POSITION cancellation - an instruction that appears on both sides in
       the residual only MOVED, and a move is a schedule choice.
    2. REGISTER stripping - cl 5.0 picks registers off a rotation cursor, so
       `mov ebx,[esi+0x84]` and `mov eax,[esi+0x84]` compute the same thing.

What survives both is the part no allocation or schedule choice explains, and
the classifier names it from the NET residual, most-actionable first:

    immediate      a constant differs                  possible semantic bug
    displacement   a member offset differs             possible layout bug
    referent       one side names a symbol the other   possible identity bug
                   never names anywhere
    selection      the mnemonic multiset differs       instruction selection
    operand        same mnemonics, different operands  term order / CSE
    arm-copy       target has one more `mov r,r`       MOSTLY REGALLOC - read
                   than the base                       the printed evidence
    extra-copy     the inverse                         MOSTLY REGALLOC, ditto
    missing-store  target repeats a member store       the arm-result temp is
    dup-store      base repeats one                    PRESENT and should not
                                                       be (memory case)
    subobject      one side splits an address into a   the SAME field, park
                   pointer + offset, the other folds
    regname        register rotation only              R1/R2, park
    schedule       a pure permutation                  park
    none           nothing survives the mask

The arm-result classes implement the detection signature of
docs/patterns/arm-result-temp-controls-copies-and-shared-store.md; `--arm`
answers the same question directly over the WHOLE stream (every member store
and every callee-saved register copy, not just the ones inside a diff chunk),
which is the sensitive form.

USE `--arm`, NOT `--kind arm-copy`. The whole `arm-copy`/`extra-copy` bucket
was read on 2026-08-23 (44 rows) and it is a REGALLOC bucket: 28 rows print an
EMPTY evidence list or a self-move (`mov edi,edi`), meaning the extra `mov r,r`
has a scratch or 8-bit destination and the callee-saved-copy signature is
absent; 11 rows were hand-read against the retail bytes and 0 were an arm
result. Read the printed evidence before believing the kind name -
`target has []` is the tool saying it found nothing. Detail and the withdrawn
"43 rows" claim: docs/patterns/equal-frame-residual-census.md.

Thirteen encoding mirrors are normalized away, because each was measured
mislabelling real rows: the addend of a RELOCATED call or jump (position
state - the referent is compared separately), cl's 2-byte `and al,imm8`
form of `and eax,0xffffff00|imm8` and its high-byte twin `and dh,imm8` for
`and edx,0xffff<imm8>ff`, `add r,-K` against `sub r,K`, `lea r,[r+K]`
against `add r,K` when the destination IS the base, `lea r,[r+r*1]`
against `add r,r`, the three-operand `lea` standing in for `inc`/`dec`
when the destination is not the source, cl's 3-byte `lea r,[r+0x0]`
alignment pad against a `nop`, the forced zero displacement of an
EBP-based or base-less memory operand, the accumulator form of an absolute
memory operand (`a1` against `8b 0d`), a referent NEITHER side has a name
for (`$anon_data_<sha>` against `FUN_<va>` - a `$E` dynamic-init helper),
and a DATA reference canonicalized to the ABSOLUTE address its
`symbol+addend` names, so a one-past-the-end array pointer that the two
sides name against different symbols cancels, and a register cl PROVED
holds zero standing in for the immediate zero (`cmp eax,ebx` for
`test eax,eax`, `push ebx` for `push 0x0`) - a dataflow fact, so an
ordinary compare between two live values still reads as one. The
referent test also
compares symbol SETS over the whole stream, so a CSE'd second load of a
global both sides name is not an identity row; and `subobject` runs the
arithmetic that register-stripping structurally cannot, so a RECT written
through `lea eax,[esi+0x20]` stops reading as four wrong member offsets.

    rom1 walls residue [--todo] [--unit U] [--max-resid N] [--kind K,...]
    rom1 walls residue --arm [...]        the arm-result worklist
    rom1 walls residue --show <rva|name>  one row, NET and EXACT residual

Cost: one objdump decode per side per row (~4 min for the ~580-row todo
queue), so it is a sweep tool. `walls diagnose` and `walls semdiff`
adjudicate the rows it flags.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher

from rom1.walls import check_unit
from rom1.walls.framescan import ESP_DISP, FRAME_IMM, LOCAL_BRANCH, frame
from rom1.walls.semdiff import BYTES_ONLY, EBP_MEM, ebp_is_frame, pair_lines

CALLEE_SAVED = ("esi", "edi", "ebx", "ebp")
REGMOV = re.compile(r"^mov\s+(e[a-z][a-z]),(e[a-z][a-z])$")
STORE = re.compile(r"^mov\s+(?:BYTE|WORD|DWORD)\s+PTR\s+\[(?!esp)([^\]]+)\],")
IMM = re.compile(r"(?<![\w\[+-])(0x[0-9a-f]{2,}|\b\d{3,}\b)")
#: read off REGISTER-STRIPPED text, where every register reads `r`
DISP = re.compile(r"\[r(?:\*\d)?(?:\+r(?:\*\d)?)?([+-]0x[0-9a-f]+)?\]")
REG = re.compile(r"\b(eax|ecx|edx|ebx|esi|edi|ebp|al|cl|dl|bl|ah|ch|dh|bh"
                 r"|ax|cx|dx|bx|si|di|bp)\b")

#: cl takes the 2-byte accumulator form when the value is in EAX and the
#: immediate's high bits are all ones, so `and al,0xe0` IS `and ecx,
#: 0xffffffe0` under a different register pick. Un-normalized, this single
#: mirror mislabelled seven ctors as an immediate difference.
ACC8 = re.compile(r"^(and|or|xor)\s+([abcd])l,0x([0-9a-f]{1,2})$")
ACC8_HIGH = {"and": "ffffff", "or": "000000", "xor": "000000"}

#: the same 2-byte form on a HIGH byte register: `and dh,0xef` masks bits
#: 8..15 and touches nothing else, so it IS `and edx,0xffffefff`.
#: `CRom1MapMgr::BuildCellAttributes` read `immediate` on this mirror alone -
#: our `and edx,0xffffefff` against retail's `and dh,0xef`, one instruction.
ACC8H = re.compile(r"^(and|or|xor)\s+([abcd])h,0x([0-9a-f]{1,2})$")
ACC8H_WRAP = {"and": ("ffff", "ff"), "or": ("0000", "00"),
              "xor": ("0000", "00")}

#: `lea ecx,[ecx+0x240]` IS `add ecx,0x240` when the destination IS the base:
#: cl picks between them on its own (LEA does not write flags), and it was
#: measured going BOTH ways against retail in one tree - the base carries the
#: `lea` on CTriggerMgr::Load and CTriggerMgr::RemoveCellRecord where retail
#: has the `add`, and the `add` on CBootyState::MoveLettersByDir and
#: CBootyState::EnterState where retail has the `lea`. Bidirectional, so it is
#: not a source lever, only noise in the immediate bucket. The zero
#: displacement is left alone: `lea ecx,[ecx+0x0]` is cl's 3-byte NOP.
LEA_ADD = re.compile(r"^lea\s+(e[a-z][a-z]),\[(e[a-z][a-z])([+-])0x([0-9a-f]+)\]$")

#: and the doubling form: `lea esi,[esi+esi*1]` IS `add esi,esi`.
LEA_DBL = re.compile(r"^lea\s+(e[a-z][a-z]),\[(e[a-z][a-z])\+(e[a-z][a-z])\*1\]$")

#: A DATA reference is `symbol + addend`, and BOTH halves are the reference:
#: the addend is not a program constant. A one-past-the-end array pointer
#: (`&g_lut16[0x100]`, the end sentinel of a `for (p = a; p != a + N; p++)`)
#: therefore names an address the delinker resolves against whatever symbol
#: STARTS there, while cl names it against the array - `cmp esi,0x200|g_lut16`
#: against `cmp esi,0x0|g_rUp`, and 0x283ca0 + 0x200 == 0x283ea0 exactly.
#: Seven rows of the `immediate` bucket were this one shape, and census
#: section 5's negative-addend twin (`&g_rasterVtxA[n-1]` resolved against the
#: array that CONTAINS it) is the same arithmetic. Canonicalizing the pair to
#: the absolute address it names can only cancel references that ARE the same
#: address, so it cannot hide a wrong claim.
ABS_TOKEN = re.compile(r"(?P<sign>[+-])?0x(?P<hex>[0-9a-f]+)")

#: objdiff disambiguates a symbol it had to name from section CONTENT, so the
#: same datum wears `$Sdata_bss_<sha>_0` in the base and a different `<sha>` in
#: the target whenever the section pools anything else - census section 6, the
#: two CFader `_kMsToSeconds` rows, which are ONE float under two section
#: hashes. The content hash is objdiff bookkeeping, not identity, so it is
#: dropped; the trailing ordinal is KEPT, because that is what distinguishes
#: two anonymous symbols of the same section.
OBJDIFF_TAG = re.compile(r"\$S\w*_[0-9a-f]{32,}_(\d+)$")
OBJDIFF_ORD = re.compile(r"\$S_\d+$")

_SYMS: dict[str, int] | None = None


def _syms() -> dict[str, int]:
    """{claimed symbol -> rva}, loaded once and fail-soft: with no Model the
    canonicalization simply does not fire and every row reads as before.

    A name claimed at MORE than one address is dropped, not picked between,
    and so is an undecorated `<id>$S` whose identifier ALSO appears under
    other claim names: `_s_gruntDirCenter$S` is one of 106 per-TU copies of
    the GruntDirStatics device, so resolving it would state an address no
    evidence supports (measured: it answers 0x2449e0 for a reference that
    the base's own arithmetic puts at 0x22aef0, a different copy)."""
    global _SYMS
    if _SYMS is None:
        try:
            from rom1.model import resolve
            seen: dict[str, int] = {}
            for b in resolve().claimed():
                if seen.get(b.name, b.rva) != b.rva:
                    seen[b.name] = -1
                else:
                    seen[b.name] = b.rva
            for name in [k for k in seen if k.endswith("$S")]:
                ident = name[:-2].lstrip("_")
                if not ident:
                    continue
                if sum(1 for k in seen if ident in k) > 1:
                    seen[name] = -1
            _SYMS = {k: v for k, v in seen.items() if v >= 0}
        except BaseException:
            _SYMS = {}
    return _SYMS


def canon_ref(asm: str, ref: str | None) -> tuple[str, str | None]:
    """Fold a DATA reference's addend into the referent as an ABSOLUTE address.

    Fires only when the operand carries EXACTLY ONE absolute token, so which
    one is the relocation's addend is not a guess: `mov DWORD PTR ds:0x0,0x5`
    (a constant stored THROUGH a relocated address) has two and is left alone,
    which is what keeps a genuinely wrong stored constant in the `immediate`
    bucket instead of moving it to `referent`."""
    if not ref:
        return asm, ref
    syms = _syms()
    rva = syms.get(ref)
    if rva is None:
        rva = syms.get(OBJDIFF_ORD.sub("$S", ref))
    if rva is None:
        return asm, ref
    hits = list(ABS_TOKEN.finditer(asm))
    if len(hits) != 1:
        return asm, ref
    m = hits[0]
    add = int(m.group("hex"), 16)
    if m.group("sign") == "-":
        add = -add
    return asm[:m.start()] + "ADDEND" + asm[m.end():], f"@{rva + add:#x}"

def ref_key(ref: str) -> str:
    """One key per DATUM, so a referent that `canon_ref` folded to an absolute
    address and one that kept its symbol name are not read as two identities.

    canon_ref only fires on an operand carrying exactly one absolute token, and
    that guard is deliberate - it is what keeps a wrong stored constant in the
    `immediate` bucket.  But it makes the fold ASYMMETRIC: our accumulator load
    `mov eax,ds:0x2bf674` has one token and becomes `@0x2bf674`, while retail's
    `cmp DWORD PTR ds:0x0,0x0` has two and keeps `?g_logicTypesRegistered@@3HA`.
    Same address, same datum, two spellings - and the referent bucket, whose
    whole job is identity, reported it as an identity difference."""
    if ref.startswith("@") or ref == "?unnamed":
        return ref
    syms = _syms()
    rva = syms.get(ref)
    if rva is None:
        rva = syms.get(OBJDIFF_ORD.sub("$S", ref))
    return f"@{rva:#x}" if rva is not None else ref


#: `add eax,0xffffffe0` IS `sub eax,0x20` - same three bytes' worth of work,
#: same value, and cl picks between them on its own (measured going BOTH ways
#: against retail in one tree: CSpotLight's ctor has the add where retail has
#: the sub, CStaticHazard's has the sub where retail has the add). Left alone,
#: the pair reads as two different constants.
ADDNEG = re.compile(r"^(add|sub)\s+(e[a-z][a-z]),0x([0-9a-f]{8})$")

#: a referent NEITHER side has a name for. objdiff calls our obj's unnamed
#: symbol `$anon_data_<sha>_N`; the delinker, with no claim on the address,
#: calls retail's `FUN_<va>` / `DAT_<va>` / `$gap_<va>`. Eleven of the fifteen
#: `referent` rows were one address under two non-names - every one a `$E`
#: dynamic-initializer helper, which the label rules deliberately never name.
UNNAMED = re.compile(r"^(FUN_|DAT_|\$gap_|\$anon_data_)")

#: LEA against the arithmetic instruction computing the same value. cl takes the
#: three-operand `lea` form for exactly one reason: the destination is not the
#: source, i.e. the source register stays live - which is the register choice
#: `reg_key` already erases. So `lea r,[r+0x1]` IS `inc r` and `lea r,[r+r*1]`
#: IS `add r,r` once the names are gone. Left un-mirrored, the lea's
#: displacement reads as a member offset the other side never touches
#: (`CRom1Mgr::RandRange`, `UpdateMgrScroll`, `CRandomAmbientSound::Update`,
#: `CMinimap::DrawBorderRaw`, `_zvec::GrowTo`). The flag side effect does
#: NOT fold: `lea` sets none, so retail's extra `test r,r` survives into the
#: residual and the row reads `selection`, which is what it is.
LEA_ARITH = {"lea r,[r+0x1]": "inc r", "lea r,[r-0x1]": "dec r",
             "lea r,[r+r*1]": "add r,r"}

#: cl's 3-byte `lea r,[r+0x0]` alignment pad, which the forced-zero rule above
#: has already shortened to `lea r,[r]`, is the same padding as a `nop`
#: (`CKitchenSlime::LoadSprites`, `CGrunt::ArrivalRecycle`,
#: `CMultiStartDlg::Watchdog`).
LEA_NOP = "lea r,[r]"

#: the accumulator form of an absolute memory operand: `a1 <addr>` prints as
#: `mov r,ds:0x0` where the general `8b 0d <addr>` prints as
#: `mov r,DWORD PTR ds:0x0`. cl takes the short form only when the value lands
#: in EAX - a register choice, not a different access.
#: the operand may already wear the canonical `ds:ADDEND` by the time the key
#: is built - the absolute-address fold rewrites it and moves the address into
#: the referent - so this must recognize BOTH spellings.  Reading only the raw
#: `ds:0x...` form silently retired the mirror when the two folds were merged.
ACCMEM = re.compile(r"^mov (r|ds:(?:0x[0-9a-f]+|ADDEND)),"
                    r"(ds:(?:0x[0-9a-f]+|ADDEND)|r)$")

#: cl 5.0 materializes a zero ONCE into a callee-saved register when a function
#: needs it repeatedly across calls, then spends it as a register everywhere an
#: immediate would otherwise appear: `cmp eax,ebx` for `test eax,eax`,
#: `mov [edi+0x4],ebx` for `mov DWORD PTR [edi+0x4],0x0`, `push ebx` for
#: `push 0x0`.  Whether it bothers is register PRESSURE, and it was measured
#: going both ways in one tree - `CStaticHazard::UpdateActiveState` and
#: `RunCustomWorldDialog` carry the immediate where retail carries the register,
#: `CMulti::PollSession` and `CPlay::LoadPlayState` the reverse - so it is noise,
#: not a source lever.
#:
#: The fold is only sound where the register PROVABLY holds zero, which is a
#: dataflow fact, not a spelling: register-stripping turns a real `cmp esi,edi`
#: between two live values into the same `cmp r,r` text.  `zero_regs` below
#: tracks it per instruction and the canonicalization consults it, so an
#: ordinary two-value compare still reads as the difference it is.
ZERO_SET = re.compile(r"^(xor|sub)\s+(e[a-z][a-z]),(e[a-z][a-z])$")
#: everything that WRITES its first operand; `cmp`/`test`/`push` and the jumps
#: are deliberately absent, and a partial write (`mov al,`) clears the whole
#: register because a zero in AL says nothing about EAX.
WRITES_DST = re.compile(
    r"^(?:mov|movzx|movsx|lea|add|adc|sub|sbb|and|or|xor|imul|shl|shr|sar|rol"
    r"|ror|inc|dec|neg|not|pop|set[a-z]{1,3}|cmov[a-z]{1,3})\s+"
    r"(e?(?:ax|cx|dx|bx|si|di|bp)|[abcd][lh])\b")
SUBREG = {"ax": "eax", "cx": "ecx", "dx": "edx", "bx": "ebx", "si": "esi",
          "di": "edi", "bp": "ebp", "al": "eax", "ah": "eax", "cl": "ecx",
          "ch": "ecx", "dl": "edx", "dh": "edx", "bl": "ebx", "bh": "ebx"}
#: a call returns in EAX and may clobber the other two scratch registers; the
#: callee-saved four survive it, which is exactly why cl parks the zero there.
CALL_CLOBBERS = ("eax", "ecx", "edx")
#: `mul`/`div` write the EDX:EAX pair without naming it, `cdq` writes EDX.
IMPLICIT_EDX_EAX = re.compile(r"^(?:mul|imul|div|idiv|cdq|cwd)\b")

CMP_ZERO = re.compile(r"^cmp\s+(.+),(e[a-z][a-z])$")
TEST_SELF = re.compile(r"^test\s+(e[a-z][a-z]),(e[a-z][a-z])$")
STORE_ZERO = re.compile(r"^mov\s+(.*\[.+\]),(e[a-z][a-z])$")
PUSH_ZERO = re.compile(r"^push\s+(e[a-z][a-z])$")


BRANCH = re.compile(r"^(jmp|j[a-z]{1,3})\s+(0x[0-9a-f]+)$")
UNCOND = re.compile(r"^(jmp|ret)\b")
ALL_REGS = frozenset(("eax", "ecx", "edx", "ebx", "esi", "edi", "ebp"))
SWEEP_CAP = 24


def _transfer(asm: str, zeros: frozenset) -> frozenset:
    if asm.startswith("call"):
        return zeros.difference(CALL_CLOBBERS)
    if IMPLICIT_EDX_EAX.match(asm):
        return zeros.difference(("eax", "edx"))
    m = WRITES_DST.match(asm)
    if m:
        dst = m.group(1)
        zeros = zeros - {SUBREG.get(dst, dst)}
    m = ZERO_SET.match(asm)
    if m and m.group(2) == m.group(3):
        zeros = zeros | {m.group(2)}
    return zeros


def zero_regs(lines):
    """Per-instruction set of registers cl has proven to hold zero.

    Returned parallel to `lines`: entry i is the set live BEFORE line i, which
    is what a use on line i reads.

    This is a real fixpoint over the function's own control flow, not a linear
    walk.  A linear walk is WRONG here and was measured being wrong: an
    early-return epilogue's `pop ebx` would retire a zero that the blocks after
    it still hold, because they are not reached through that epilogue.  An
    instruction with no known predecessor - a jump-table arm, whose target the
    text does not name - starts from the empty set, so an unproven register is
    never spent."""
    by_addr = {ln.addr: i for i, ln in enumerate(lines) if ln.addr is not None}
    succ = [[] for _ in lines]
    preds = [[] for _ in lines]
    for i, ln in enumerate(lines):
        asm = ln.asm or ""
        m = BRANCH.match(asm)
        if m:
            j = by_addr.get(int(m.group(2), 16))
            if j is not None:
                succ[i].append(j)
        if not UNCOND.match(asm) and i + 1 < len(lines):
            succ[i].append(i + 1)
    for i, ss in enumerate(succ):
        for j in ss:
            preds[j].append(i)

    # A must-analysis descends from the top element: start every OUT holding
    # every register and let the intersections retire them.  Seeded at the
    # empty set instead, the meet would keep it empty and prove nothing.
    ins = [ALL_REGS for _ in lines]
    outs = [ALL_REGS for _ in lines]
    for _ in range(SWEEP_CAP):
        changed = False
        for i, ln in enumerate(lines):
            if i == 0 or not preds[i]:
                new_in = frozenset()
            else:
                new_in = frozenset.intersection(*(outs[p] for p in preds[i]))
            new_out = _transfer(ln.asm or "", new_in)
            if new_in != ins[i] or new_out != outs[i]:
                ins[i], outs[i] = new_in, new_out
                changed = True
        if not changed:
            return ins
    # Not converged: the descent is monotone, so an unfinished run may still be
    # holding a register a back edge would retire.  Prove nothing rather than
    # spend a zero we have not established.
    return [frozenset() for _ in lines]


def spend_zero(asm: str, zeros) -> str:
    """Rewrite a use of a proven-zero register as the immediate it stands in
    for, so the two spellings of the same constant compare equal.

    `test r,r` is folded unconditionally: it is cl's encoding of a compare
    against an immediate zero, and naming it that way is what lets the
    register-spelled compare meet it."""
    m = TEST_SELF.match(asm)
    if m and m.group(1) == m.group(2):
        return f"cmp {m.group(1)},0x0"
    if not zeros:
        return asm
    m = CMP_ZERO.match(asm)
    if m and m.group(2) in zeros and m.group(1) != m.group(2):
        return f"cmp {m.group(1)},0x0"
    m = STORE_ZERO.match(asm)
    if m and m.group(2) in zeros:
        return f"mov {m.group(1)},0x0"
    m = PUSH_ZERO.match(asm)
    if m and m.group(1) in zeros:
        return "push 0x0"
    return asm


def strip_regs(asm: str) -> str:
    return REG.sub("r", asm)


def mirror(asm: str) -> str:
    m = ACC8.match(asm)
    if m:
        return (f"{m.group(1)} e{m.group(2)}x,"
                f"0x{ACC8_HIGH[m.group(1)]}{int(m.group(3), 16):02x}")
    m = ACC8H.match(asm)
    if m:
        hi, lo = ACC8H_WRAP[m.group(1)]
        return (f"{m.group(1)} e{m.group(2)}x,"
                f"0x{hi}{int(m.group(3), 16):02x}{lo}")
    m = ADDNEG.match(asm)
    if m and int(m.group(3), 16) >= 0x80000000:
        flip = "sub" if m.group(1) == "add" else "add"
        return f"{flip} {m.group(2)},0x{0x100000000 - int(m.group(3), 16):x}"
    m = LEA_ADD.match(asm)
    if m and m.group(1) == m.group(2) and int(m.group(4), 16):
        op = "add" if m.group(3) == "+" else "sub"
        return mirror(f"{op} {m.group(1)},0x{m.group(4)}")
    m = LEA_DBL.match(asm)
    if m and m.group(1) == m.group(2) == m.group(3):
        return f"add {m.group(1)},{m.group(1)}"
    return asm


def masked(lines, self_name: str = "",
           ebp_frame: bool | None = None) -> list[str]:
    """framescan's mask (esp displacements, branch targets, the frame
    immediate) plus the relocated-call addend and the accumulator mirror.

    A function's own jump/index table decodes as junk instructions carrying
    huge displacements and a relocation back to the function; `semdiff._decode`
    drops it by the offsets its relocations cover, and this filter is the older
    referent-shaped form of the same rule.

    Where cl gave the function an EBP FRAME, `[ebp+-N]` is a stack slot and not
    a member displacement, so it masks like `[esp+N]` - otherwise a pure frame
    shift reads as `displacement`, i.e. "possible layout bug". Eight rows of the
    595-row todo queue establish one; three address slots through it. Pass
    `ebp_frame` from BOTH sides: one side can have an ebp frame where the other
    does not, and masking only that side manufactures a difference."""
    out = []
    zeros = zero_regs(lines)
    if ebp_frame is None:
        ebp_frame = ebp_is_frame(lines)
    for ln, live in zip(lines, zeros):
        if self_name and ln.ref == self_name:
            continue
        asm = ESP_DISP.sub("[esp+?]", spend_zero(ln.asm, live))
        if ebp_frame:
            asm = EBP_MEM.sub("[esp+?]", asm)
        if not asm or BYTES_ONLY.match(asm):
            continue
        if LOCAL_BRANCH.match(asm):
            asm = asm.split()[0] + " L"
        if FRAME_IMM.match(asm):
            asm = "FRAME"
        ref = "?unnamed" if ln.ref and UNNAMED.match(ln.ref) else ln.ref
        if ref:
            ref = OBJDIFF_TAG.sub(r"$S_\1", ref)
        asm, ref = canon_ref(mirror(asm), ref)
        out.append(asm + (f"|{ref}" if ref else ""))
    return out


def residual_of(base_m: list[str], tgt_m: list[str]):
    ops = SequenceMatcher(None, base_m, tgt_m, autojunk=False).get_opcodes()
    chunks, resid = [], 0
    for op, i1, i2, j1, j2 in ops:
        if op == "equal":
            continue
        resid += max(i2 - i1, j2 - j1)
        chunks.append({"op": op, "b": base_m[i1:i2], "t": tgt_m[j1:j2],
                       "bi": i1, "ti": j1})
    return resid, chunks


def bare(asm: str) -> str:
    """The instruction without its relocation referent."""
    return asm.split("|")[0]


def reg_key(asm: str) -> str:
    """Register-stripped, but the REFERENT is kept: two loads of different
    globals are not the same tuple however the registers land.

    The forced zero displacement folds here and only here: which base register
    cl picked is exactly what this key is meant to erase, and `[ebp+0x0]`
    addresses what `[ecx]` addresses. The LEA-for-arithmetic and accumulator
    memory forms fold for the same reason: each is chosen by which register the
    value landed in."""
    head, sep, ref = asm.partition("|")
    key = strip_regs(head).replace("+0x0]", "]")
    key = LEA_ARITH.get(key, "nop" if key == LEA_NOP else key)
    if ACCMEM.match(key):
        key = key.replace("ds:", "DWORD PTR ds:")
    return key + sep + ref


def net_residual(chunks):
    """(base lines, target lines, exact-only, net-after-register-stripping)."""
    bo = [x for c in chunks for x in c["b"]]
    to = [x for c in chunks for x in c["t"]]
    exact_b, exact_t = Counter(bo) - Counter(to), Counter(to) - Counter(bo)
    kb = Counter(reg_key(x) for x in exact_b.elements())
    kt = Counter(reg_key(x) for x in exact_t.elements())
    return bo, to, exact_b, exact_t, kb - kt, kt - kb


def disp(d: str) -> str:
    """An x86 memory operand with EBP as its base, or with a scaled index and
    no base at all, CANNOT encode without a displacement byte/dword, so cl
    writes `[ebp+0x0]` / `[eax*8+0x0]` for the same address `[ecx]` / `[eax*8]`
    encodes bare. Register-stripping erases which base it was, so an explicit
    zero reads as a member-offset difference: a quarter of the `displacement`
    bucket was this one encoding."""
    return "" if d in ("+0x0", "-0x0") else d


#: an instruction that MATERIALIZES a pointer at a constant offset - the K of
#: `mov ecx,[esi+0x38]; add ecx,0x1a0; mov eax,[ecx+0x28]` against the folded
#: `mov eax,[esi+0x1c8]`. 0x1a0 + 0x28 == 0x1c8, the SAME field.
PTR_BASE = re.compile(r"^(?:lea r,\[r(?:\+r(?:\*\d)?)?([+-]0x[0-9a-f]+)\]"
                      r"|add r,(0x[0-9a-f]+))$")


def _disps(lines) -> Counter:
    """displacement VALUES of every memory operand in `lines`, `[r]` as 0."""
    return Counter(int(d, 16) if d else 0
                   for x in lines for d in DISP.findall(x))


def subobject_shift(only_b, only_t, base_m, tgt_m):
    """(K, n) when one side SPLITS an address into a sub-object pointer plus a
    member offset and the other folds the whole thing into one displacement.

    Register-stripping cannot prove the sum, so the two sides read as different
    member offsets; the arithmetic is what settles it, and it settled
    CImage::RenderImage (a RECT at +0x20 written through `lea eax,[esi+0x20]`),
    CRom1Mgr::RecomputeViewScale, CNetSession::SendOne (`[r+r+0x3b0]` then
    `[r+0x4]` against `[r+r+0x3b4]`) and CBattlezMapConfig::ClaimCellFromRow
    (`lea [r+r*8+0x188]` then `[r+0xd4]` against `[r+r*8+0x25c]`).

    K is drawn from a pointer-materializing `lea`/`add` ANYWHERE in either
    stream, because the lea is often a line both sides share. `n` is how many
    displacements the shift reconciles: a LONE pair is exactly the wrong-field
    signature this bucket exists to find, so the caller must not clear one."""
    db, dt = _disps(only_b), _disps(only_t)
    if not db or not dt:
        return None
    ks = {int(m.group(1) or m.group(2), 16)
          for x in base_m + tgt_m
          if (m := PTR_BASE.match(strip_regs(bare(x))))}
    for k in sorted(ks - {0}):
        for split, fold in ((db, dt), (dt, db)):
            s = Counter(split)
            if s[k]:                       # the materializing lea's own K
                s -= Counter({k: 1})
            if Counter({v + k: n for v, n in s.items()}) == fold:
                return k, sum(fold.values())
    return None


def classify(chunks, base_m, tgt_m):
    bo, to, exact_b, exact_t, net_b, net_t = net_residual(chunks)
    if not bo and not to:
        return "none", ""
    if not exact_b and not exact_t:
        return "schedule", f"{len(bo)} insns permuted"
    if not net_b and not net_t:
        return "regname", (f"{sum(exact_b.values())}/{sum(exact_t.values())}"
                           f" insns, register rotation")

    deficit = sum(net_t.values()) - sum(net_b.values())
    t_copies = [x for x in net_t.elements() if x == "mov r,r"]
    b_copies = [x for x in net_b.elements() if x == "mov r,r"]
    only_b = [bare(x) for x in net_b.elements()]
    only_t = [bare(x) for x in net_t.elements()]
    raw = lambda c: sorted({x for x in c.elements()                # noqa: E731
                            if (m := REGMOV.match(bare(x)))
                            and m.group(1) in CALLEE_SAVED})
    if deficit > 0 and len(t_copies) >= deficit and not b_copies:
        return "arm-copy", f"+{deficit}: target has {raw(exact_t)}"
    if deficit < 0 and len(b_copies) >= -deficit and not t_copies:
        return "extra-copy", f"{deficit}: base has {raw(exact_b)}"

    b_stores = [x for x in only_b if STORE.match(x)]
    t_stores = [x for x in only_t if STORE.match(x)]
    if deficit < 0 and len(b_stores) >= -deficit and not t_stores:
        dup = sorted({x for x in exact_b.elements()
                      if STORE.match(bare(x)) and base_m.count(x) > 1})
        if dup:
            return "dup-store", f"{deficit}: base repeats {dup}"
        return "extra-store", f"{deficit}: base-only {sorted(set(b_stores))}"
    if deficit > 0 and len(t_stores) >= deficit and not b_stores:
        return "missing-store", f"+{deficit}: target-only {sorted(set(t_stores))}"

    bi = Counter(m for x in only_b for m in IMM.findall(x))
    ti = Counter(m for x in only_t for m in IMM.findall(x))
    if bi != ti:
        return "immediate", (f"base {sorted((bi - ti).elements())} vs target "
                             f"{sorted((ti - bi).elements())}")
    bd = Counter(disp(d) for x in only_b for d in DISP.findall(x))
    td = Counter(disp(d) for x in only_t for d in DISP.findall(x))
    if bd != td:
        note = (f"base {sorted((bd - td).elements())} vs target"
                f" {sorted((td - bd).elements())}")
        shift = subobject_shift(only_b, only_t, base_m, tgt_m)
        if shift:
            note += f"  [sub-object {shift[0]:+#x} over {shift[1]}]"
            # a LONE pair reconciled by some constant is exactly the wrong-field
            # signature; only a run of them is evidence of a split address.
            if shift[1] >= 2:
                return "subobject", note
        return "displacement", note
    br = Counter(ref_key(x.split("|", 1)[1])
                 for x in exact_b.elements() if "|" in x)
    tr = Counter(ref_key(x.split("|", 1)[1])
                 for x in exact_t.elements() if "|" in x)
    # A COUNT difference on a symbol both sides reference is CSE or
    # rematerialization, not an identity question - only a symbol the other
    # side never names anywhere is a claim to check.
    seen_b = {ref_key(x.split("|", 1)[1]) for x in base_m if "|" in x}
    seen_t = {ref_key(x.split("|", 1)[1]) for x in tgt_m if "|" in x}
    only_br = sorted(r for r in (br - tr) if r not in seen_t)
    only_tr = sorted(r for r in (tr - br) if r not in seen_b)
    if only_br or only_tr:
        return "referent", f"base {only_br} vs target {only_tr}"
    if Counter(x.split()[0] for x in only_b) != \
       Counter(x.split()[0] for x in only_t):
        return "selection", f"{sorted(only_b)} vs {sorted(only_t)}"
    return "operand", f"{sorted(only_b)} vs {sorted(only_t)}"


def store_census(stream):
    """Member stores keyed on the DESTINATION only, so `mov [esi+0x4c],ecx`
    and `mov [esi+0x4c],edx` are one store. A count that differs between the
    sides is the arm-result MEMORY signature."""
    c = Counter()
    for x in stream:
        m = STORE.match(bare(x))
        if m:
            c[strip_regs(m.group(1))] += 1
    return c


def copy_census(stream):
    return sum(1 for x in stream
               if (m := REGMOV.match(bare(x))) and m.group(1) in CALLEE_SAVED)


def scan_one(rva: str) -> dict:
    binding, base, target = pair_lines(rva)
    base_res, base_push = frame(base)
    tgt_res, tgt_push = frame(target)
    ebp = ebp_is_frame(base, target)
    mb = masked(base, binding.name, ebp)
    mt = masked(target, binding.name, ebp)
    residual, chunks = residual_of(mb, mt)
    kind, note = classify(chunks, mb, mt)
    sb, st = store_census(mb), store_census(mt)
    return {"base_frame": base_res, "tgt_frame": tgt_res,
            "base_push": base_push, "tgt_push": tgt_push,
            "base_insns": len(mb), "tgt_insns": len(mt),
            "residual": residual, "kind": kind, "note": note[:220],
            "store_delta": {k: [sb[k], st[k]]
                            for k in set(sb) | set(st) if sb[k] != st[k]},
            "base_copies": copy_census(mb), "tgt_copies": copy_census(mt),
            "chunks": chunks}


def scan(rows, progress=None):
    out = []
    for n, row in enumerate(rows, 1):
        rec = {k: row.get(k) for k in ("rva", "unit", "symbol", "cur",
                                       "hist_max")}
        try:
            rec.update(scan_one(row["rva"]))
        except BaseException as err:              # SystemExit from the locator
            rec["error"] = str(err)[:120]
        out.append(rec)
        if progress and n % 50 == 0:
            print(f"  ... {n}/{len(rows)}", file=progress)
    return out


ORDER = ["immediate", "displacement", "referent", "selection", "operand",
         "arm-copy", "dup-store", "missing-store", "extra-store",
         "extra-copy", "subobject", "regname", "schedule", "none"]


def report(rows, max_resid, kinds, limit):
    ok = [r for r in rows if "kind" in r]
    eq = [r for r in ok if r["base_frame"] == r["tgt_frame"]]
    sel = [r for r in eq if r["residual"] <= max_resid]
    print(f"paired rows read: {len(ok)}   (errors {len(rows) - len(ok)})")
    print(f"  frame EQUAL to retail's : {len(eq)}")
    print(f"  of those, residual <= {max_resid} : {len(sel)}")
    print()
    counts = Counter(r["kind"] for r in sel)
    for k in ORDER:
        if counts[k]:
            print(f"  {k:<14} {counts[k]:4d}")
    print()
    shown = [r for r in sel if not kinds or r["kind"] in kinds]
    shown.sort(key=lambda r: (ORDER.index(r["kind"]) if r["kind"] in ORDER
                              else 99, r["residual"], -r["cur"]))
    print(f"{'rva':>10} {'cur':>7} {'res':>4} {'nB':>5} {'nT':>5} "
          f"{'kind':<14} unit/symbol")
    for r in shown[:limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f} {r['residual']:4d} "
              f"{r['base_insns']:5d} {r['tgt_insns']:5d} {r['kind']:<14} "
              f"{r['unit']}/{r['symbol'][:44]}")
        if r["note"]:
            print(f"           {r['note']}")


def arm_report(rows, limit):
    """The arm-result-temp worklist, measured over the WHOLE stream."""
    ok = [r for r in rows if "kind" in r]
    mem = [r for r in ok if r["store_delta"]]
    reg = [r for r in ok if r["base_copies"] != r["tgt_copies"]]
    print(f"paired rows read: {len(ok)}")
    print(f"  MEMORY case   (a member store one side duplicates) : {len(mem)}")
    print(f"  REGISTER case (callee-saved copy count differs)    : {len(reg)}")
    print()
    print("== MEMORY: `target > base` means retail writes the member PER ARM "
          "and we share it ==")
    for r in sorted(mem, key=lambda x: -x["cur"])[:limit]:
        total = sum(v[1] - v[0] for v in r["store_delta"].values())
        print(f"{r['rva']:>10} {r['cur']:7.2f} "
              f"{'T+' if total > 0 else 'B+'}{abs(total):<3d} "
              f"{r['unit']}/{r['symbol'][:46]}")
        for k, v in sorted(r["store_delta"].items()):
            print(f"           {k:<22} base {v[0]}  target {v[1]}")
    print()
    print("== REGISTER: `target > base` means the arm temp cl would copy to a "
          "callee-saved register is MISSING ==")
    for r in sorted(reg, key=lambda x: -x["cur"])[:limit]:
        print(f"{r['rva']:>10} {r['cur']:7.2f} base {r['base_copies']:3d} "
              f"target {r['tgt_copies']:3d}  {r['kind']:<13} "
              f"{r['unit']}/{r['symbol'][:44]}")


def show(rva: str) -> None:
    rec = scan_one(rva)
    print(f"{rva}  frame {rec['base_frame']}/{rec['tgt_frame']}  push "
          f"{rec['base_push']}/{rec['tgt_push']}  insns "
          f"{rec['base_insns']}/{rec['tgt_insns']}")
    print(f"  residual {rec['residual']}  kind {rec['kind']}")
    print(f"  {rec['note']}")
    _bo, _to, eb, et, nb, nt = net_residual(rec["chunks"])
    print("  -- NET (position-cancelled, register-stripped) --")
    for x in sorted(nb.elements()):
        print(f"    b< {x}")
    for x in sorted(nt.elements()):
        print(f"    t> {x}")
    print("  -- EXACT-ONLY --")
    for x in sorted(eb.elements()):
        print(f"    B< {x}")
    for x in sorted(et.elements()):
        print(f"    T> {x}")
    if rec["store_delta"]:
        print("  -- member stores whose COUNT differs --")
        for k, v in sorted(rec["store_delta"].items()):
            print(f"    {k:<22} base {v[0]}  target {v[1]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls residue",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("--show", metavar="RVA", help="one row, in full")
    ap.add_argument("--unit", help="restrict to one unit of config/units.toml")
    ap.add_argument("--todo", action="store_true",
                    help="the campaign queue rather than every sub-100 row")
    ap.add_argument("--below", type=float, default=100.0)
    ap.add_argument("--max-resid", type=int, default=10 ** 6)
    ap.add_argument("--kind", help="comma-separated kinds to list")
    ap.add_argument("--arm", action="store_true",
                    help="the arm-result-temp worklist instead")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.show:
        show(args.show)
        return 0

    from rom1.walls.inventory import build
    rows = build(check_unit(args.unit), args.below, args.todo)
    scanned = scan(rows, progress=None if args.json else sys.stderr)
    if args.json:
        json.dump(scanned, sys.stdout)
        return 0
    if args.arm:
        arm_report(scanned, args.limit)
        return 0
    report(scanned, args.max_resid,
           set(args.kind.split(",")) if args.kind else None, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
