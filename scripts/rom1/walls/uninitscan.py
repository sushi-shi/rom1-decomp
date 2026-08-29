"""rom1.walls.uninitscan - the CONDITIONALLY-UNINITIALIZED LOCAL sieve.

A reconstruction that leaves a local unwritten on some path is either FAITHFUL
- retail's own code has the hole and reads the slot anyway - or an ACCIDENT of
transcription that happens to compile because cl coalesced the halves onto a
register that was live. The first is evidence about the SOURCE and must be
kept; the second is a reader trap. Telling them apart needs two things this
verb puts side by side: the hole, and the function's current score.

CGrunt::ClaimSwitchTile 0x52c70 is the faithful case and the reason the verb
exists: its `ja` default arm loads the destination from frame slots NOTHING in
the function ever writes, which is what dates the declaration as carrying no
initializer ([[switch-destination-is-scalars-not-an-aggregate]]).
CTriggerMgr::LoadCameraSprite 0x78960 is the same fact at 100.00 and is the
cleanest picture of it in the image:

    je   0x789a2                 ; pos == 0
    jle  0x789ad                 ; pos < 0  -> the join
    cmp  eax,0x2
    jg   0x789ad                 ; pos > 2  -> the join
    lea  eax,[ecx-0x28] ...
  0x789ad:
    mov  eax,DWORD PTR [esp+0x4] ; BOTH halves read the SAME
    mov  ecx,DWORD PTR [esp+0x4] ; never-written slot

Two uninitialized locals cl coalesced onto one home. Retail shipped that.

WHY NOT THE ERA COMPILER. Measured 2026-08-23 on cl 5.0 SP3: a local assigned
in one arm and read after the `if` is SILENT at /W1, /W3 and /W4, while a local
never assigned on any path warns C4700 at all three. cl 5.0 has no
flow-sensitive C4701, so the interesting class is invisible to it and a sweep
of all 282 TUs at /W4 reports zero. clang-cl over the clangd compilation
database does have it.

AND ITS MEASURED REACH. clang reports the SCALAR case and NOT a struct member:
a probe with `i32 s; Coord a; if (c) { s = 7; a.m_x = 8; } use(s + a.m_x);`
warns about `s` and says nothing about `a.m_x`. So an uninitialized AGGREGATE
half - exactly ClaimSwitchTile's shape before it was modelled as scalars - is
below this instrument. `--control` re-proves both halves of that statement, and
a zero from this sieve means "no scalar holes", never "no holes".

READ THE OUTPUT BY SCORE. A hit inside a function already at 100.00 is FAITHFUL
by construction: the bytes are retail's, so the hole is retail's. Of the 28
hits in the 2026-08-23 tree, 16 are such rows across 11 functions. The 12 below
100 are the worklist, and three of them (ClaimSwitchTile's `nextX`/`nextY`) are
already proven faithful by the default-arm evidence.

    rom1 walls uninitscan [--file SUBSTR] [--control] [--all]
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from rom1.core.paths import BUILD, REPO

DB = BUILD / "clangd/compile_commands.json"
WANT = re.compile(r"\[-W(sometimes-uninitialized|conditional-uninitialized"
                  r"|uninitialized)\]")
HIT = re.compile(r"^(.+?)\((\d+),\d+\)\s*:\s*warning: (.*?) \[-W(\S+)\]")
RVA_PIN = re.compile(r"^\s*RVA\w*\((0x[0-9a-fA-F]+)")
FLAGS = ["-fsyntax-only", "-Wconditional-uninitialized",
         "-Wsometimes-uninitialized", "-Wuninitialized"]

PROBE = """struct Probe { int m_x; int m_y; };
int probe(int c) {
    int scalar;
    Probe agg;
    if (c) { scalar = 7; agg.m_x = 8; }
    return scalar + agg.m_x;
}
"""


def clang_cl() -> str:
    cc = shutil.which("clang-cl")
    if not cc:
        print("[uninitscan] no clang-cl on PATH - this verb needs the dev "
              "shell's clang", file=sys.stderr)
        raise SystemExit(2)
    return cc


def entries():
    if not DB.is_file():
        print(f"[uninitscan] no compilation database at {DB} - run "
              "`rom1 build` (it emits the clangd database)", file=sys.stderr)
        raise SystemExit(2)
    for e in json.load(open(DB)):
        if e["file"].endswith(".cpp") and e["file"].startswith("src/"):
            yield e


def run_one(cc: str, entry) -> list[str]:
    args = [a for a in entry["arguments"] if a != "/c"]
    args[0] = cc
    r = subprocess.run(args + FLAGS, cwd=entry["directory"],
                       capture_output=True, text=True)
    return [ln.strip() for ln in r.stderr.splitlines() if WANT.search(ln)]


def control() -> bool:
    """Re-prove BOTH halves of the reach statement: the scalar half is
    reported, the aggregate-member half is not. A sieve whose answer is a
    count of zero has to answer this first."""
    cc = clang_cl()
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / "probe.cpp"
        src.write_text(PROBE)
        r = subprocess.run([cc, "/c", str(src), "--target=i386-pc-windows-msvc",
                            *FLAGS], cwd=d, capture_output=True, text=True)
        hits = [ln for ln in r.stderr.splitlines() if WANT.search(ln)]
    scalar = any("'scalar'" in ln for ln in hits)
    aggregate = any("'agg'" in ln for ln in hits)
    print(f"  {'OK  ' if scalar else 'FAIL'} scalar half reported"
          f"        ({len(hits)} warning line(s))")
    print(f"  {'OK  ' if not aggregate else 'FAIL'} aggregate half NOT reported"
          f"  (the measured blind spot)")
    return scalar and not aggregate


def owner(path: pathlib.Path, lineno: int):
    """The RVA pin above `lineno` - the function the hit belongs to."""
    try:
        src = path.read_text().splitlines()
    except OSError:
        return None
    for i in range(min(lineno, len(src)) - 1, -1, -1):
        m = RVA_PIN.match(src[i])
        if m:
            return int(m.group(1), 16)
    return None


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="rom1 walls uninitscan", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="substring of the source path")
    ap.add_argument("--control", action="store_true",
                    help="re-prove the detector's reach and stop")
    ap.add_argument("--all", action="store_true",
                    help="also list the rows already at 100%% (faithful)")
    a = ap.parse_args(argv)
    if a.control:
        return 0 if control() else 1

    cc = clang_cl()
    from rom1.model import resolve
    from rom1.walls.inventory import report_scores
    _p, scores = report_scores()
    by_rva = {b.rva: (b.unit, b.name) for b in resolve().functions if b.name}

    rows, n = [], 0
    for e in entries():
        if a.file and a.file not in e["file"]:
            continue
        n += 1
        for ln in run_one(cc, e):
            m = HIT.match(ln)
            if not m:
                continue
            path = pathlib.Path(m.group(1))
            try:
                rel = path.relative_to(REPO)
            except ValueError:
                rel = path
            rva = owner(path if path.is_absolute() else REPO / path,
                        int(m.group(2)))
            unit, sym = by_rva.get(rva, ("?", "?"))
            rows.append((scores.get((unit, sym), -1.0), rva, unit, sym,
                         str(rel), int(m.group(2)), m.group(3), m.group(4)))

    faithful = [r for r in rows if r[0] >= 100.0]
    work = [r for r in rows if r[0] < 100.0]
    print(f"{n} TU(s); {len(rows)} hit(s): {len(work)} below 100%, "
          f"{len(faithful)} inside functions already at 100% (FAITHFUL - the "
          f"bytes are retail's, so the hole is retail's)")
    for title, group in ((f"WORKLIST (score < 100)", work),
                         ("FAITHFUL (score == 100)",
                          faithful if a.all else [])):
        if not group and title.startswith("FAITHFUL"):
            continue
        print(f"\n{title}: {len(group)}")
        for pct, rva, unit, sym, f, lineno, msg, flag in sorted(group):
            score = "  n/a" if pct < 0 else f"{pct:6.2f}"
            addr = f"0x{rva:06x}" if rva is not None else "        "
            print(f"  {score} {addr} {unit:20s} {f}:{lineno}  "
                  f"{sym[:44]}  [{flag}]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
