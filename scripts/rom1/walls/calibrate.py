"""rom1.walls.calibrate - the reflexivity control the paired sieves lacked.

    rom1 walls calibrate [--stride N] [--limit N] [--sieve NAME] [--json]

WHAT THIS TESTS, AND WHAT IT STRUCTURALLY CANNOT.

An EXACT row is byte-identical in the sense objdiff scores, so every quantity a
sieve derives FROM THE BYTES is equal on both sides by construction - a frame
size, a member offset, a loop span, an instruction count, a condition code.
Running a byte-keyed comparison over exact rows therefore tests exactly one
thing: that the comparison is reflexive.  It can say NOTHING about whether the
key is COMPARABLE between two builds that differ, and that is where the defects
live (`walls valuetemp` compared frame offsets and `walls storescan` compared
frame-based store runs; neither could ever fire here).

Reflexivity is not vacuous, though, and that is the point of this module. The
two sides are different ARTIFACTS - cl's own object and the delinker's - and
their RELOCATION tables differ in presence and spelling even where the score is
100.00.  Every paired sieve filters on `Line.ref`, so an asymmetric referent
reads as a residual on a function that is already byte-perfect.

Measured 2026-08-23 over 940 exact rows: TWO fired, and both were the same
previously-unseen defect.  `zPTree::Walk` (0x193340) and
`CDDrawSubMgrLeaf::ScanTree` (0x152ad0) are recursive; our object spells the
recursive call as a `call rel32` with a relocation naming the function, the
delinked target resolves it inside its own section and leaves no relocation at
all, so `walls residue` dropped the line on one side and kept it on the other
and reported a one-instruction `selection` residual on a byte-identical body.
`walls thisscan` had already met this asymmetry from the other end (its own
calibration found ten inverse sites that were the caller calling ITSELF); the
normalization now lives in `semdiff._decode` and covers every consumer.

So: a green run here means the referent filters are symmetric.  It does not
mean a sieve measures anything.  For that, read each sieve's own negative
control and its statement of what its key is comparable to.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from difflib import SequenceMatcher

from rom1.walls.inventory import report_scores
from rom1.walls.semdiff import (ebp_is_frame, exclusive, features,
                                  pair_lines)
from rom1.walls import framescan, jccscan, loopscan, residue, storescan

SIEVES = ("framescan", "loopscan", "jccscan", "storescan", "residue")


def check(binding, base, tgt) -> dict:
    """Every cell must be 0/False on a byte-identical pair."""
    name = binding.name
    fb, pb = framescan.frame(base)
    ft, pt = framescan.frame(tgt)
    mb = framescan.masked(base, name)
    mt = framescan.masked(tgt, name)
    ops = SequenceMatcher(None, mb, mt, autojunk=False).get_opcodes()
    fs_resid = sum(max(i2 - i1, j2 - j1)
                   for op, i1, i2, j1, j2 in ops if op != "equal")

    lb, lt = loopscan.loops(base, name), loopscan.loops(tgt, name)
    pairs, unpaired = loopscan.pair(lb, lt)

    rb = storescan.store_runs(base, 3)
    rt = storescan.store_runs(tgt, 3)
    ebp = ebp_is_frame(base, tgt)
    gb, gt = features(base, name, ebp), features(tgt, name, ebp)

    rmb = residue.masked(base, name, ebp)
    rmt = residue.masked(tgt, name, ebp)
    resid, chunks = residue.residual_of(rmb, rmt)
    kind, note = residue.classify(chunks, rmb, rmt)

    return {
        "framescan.frame": fb - ft,
        "framescan.push": pb - pt,
        "framescan.residual": fs_resid,
        "loopscan.count": len(lb) - len(lt),
        "loopscan.unpaired": unpaired,
        "loopscan.span": sum(1 for a, c in pairs if a["span"] != c["span"]),
        "jccscan.codes": int(jccscan.codes(base) != jccscan.codes(tgt)),
        "storescan.runs": len(rb) - len(rt),
        "storescan.permuted": len(storescan.permuted(rb, rt)),
        "storescan.exclusive": len(exclusive(gb, gt)),
        "residue.residual": resid,
        "residue.kind": 0 if kind == "none" else 1,
        "_note": note[:150] if kind != "none" else "",
    }


CELLS = ("framescan.frame", "framescan.push", "framescan.residual",
         "loopscan.count", "loopscan.unpaired", "loopscan.span",
         "jccscan.codes",
         "storescan.runs", "storescan.permuted", "storescan.exclusive",
         "residue.residual", "residue.kind")


def run(stride: int, sieve: str | None, progress=None):
    from rom1.model import resolve
    _p, scores = report_scores()
    by_name = {(b.unit, b.name): b for b in resolve().functions if b.name}
    exact = sorted((u, s) for (u, s), pct in scores.items() if pct >= 100.0)
    exact = exact[::stride]
    rows, errors = [], 0
    for n, (u, s) in enumerate(exact, 1):
        b = by_name.get((u, s))
        if b is None:
            continue
        try:
            binding, base, tgt = pair_lines(f"0x{b.rva:x}")
            rec = check(binding, base, tgt)
        except BaseException:
            errors += 1
            continue
        rec.update(rva=f"0x{b.rva:06x}", unit=u, symbol=s)
        rows.append(rec)
        if progress and n % 200 == 0:
            print(f"  ... {n}/{len(exact)}", file=progress)
    if sieve:
        keep = [c for c in CELLS if c.startswith(sieve + ".")]
        for r in rows:
            for c in CELLS:
                if c not in keep:
                    r[c] = 0
    return rows, errors, len(exact)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 walls calibrate",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("--stride", type=int, default=4,
                    help="sample every Nth exact row (1 = all ~6500)")
    ap.add_argument("--sieve", choices=SIEVES, help="one sieve's cells only")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    rows, errors, total = run(a.stride, a.sieve,
                              progress=None if a.json else sys.stderr)
    if a.json:
        json.dump(rows, sys.stdout)
        return 0

    fired = Counter()
    for r in rows:
        for c in CELLS:
            if r[c]:
                fired[c] += 1
    print(f"exact rows in the report: {total} (stride {a.stride}) - "
          f"decoded {len(rows)}, unreadable {errors}")
    print("every cell below must be 0; a hit is a DETECTOR bug, never a "
          "reconstruction one\n")
    for c in CELLS:
        print(f"  {c:24} {fired[c]:5d}")
    bad = [r for r in rows if any(r[c] for c in CELLS)]
    print(f"\nrows firing any cell: {len(bad)}")
    for r in sorted(bad, key=lambda x: x["rva"])[:a.limit]:
        hits = ", ".join(f"{c}={r[c]}" for c in CELLS if r[c])
        print(f"  {r['rva']} {r['unit']}/{r['symbol'][:52]}\n      {hits}"
              + (f"\n      {r['_note']}" if r["_note"] else ""))
    print("\nREAD THIS AS WHAT IT IS: a reflexivity control over the referent "
          "filters.\nA byte-keyed comparison is equal on an exact row BY "
          "CONSTRUCTION, so a clean run\nhere says nothing about whether a key "
          "is comparable between two DIFFERENT builds.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
