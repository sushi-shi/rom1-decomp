"""Regenerate and verify the checked-in Vostok relocation manifest."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from rom1.core.paths import BUILD, REPO, RETAIL, retail_exe


GENERATOR = REPO / "scripts/find_relocs.py"
TRACKED = RETAIL / "relocs.tsv"
CANDIDATE = BUILD / "gen/relocs.tsv"


def _rows(path: Path) -> list[str]:
    lines = [line for line in path.read_text().splitlines()
             if line and not line.startswith("#")]
    if not lines or lines[0] != "site_rva\tkind":
        raise ValueError(f"{path}: invalid reloc-manifest header")
    seen: set[int] = set()
    previous = -1
    for number, line in enumerate(lines[1:], 2):
        fields = line.split("\t")
        if len(fields) != 2 or fields[1] != "dir32":
            raise ValueError(f"{path}:{number}: expected site_rva<TAB>dir32")
        rva = int(fields[0], 0)
        if rva in seen:
            raise ValueError(f"{path}:{number}: duplicate site RVA {rva:#x}")
        if rva <= previous:
            raise ValueError(f"{path}:{number}: sites are not strictly sorted")
        seen.add(rva)
        previous = rva
    return lines


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="replace config/retail/relocs.tsv on drift")
    parser.add_argument("--exe", type=Path, default=retail_exe())
    parser.add_argument("--generator", type=Path, default=GENERATOR)
    args = parser.parse_args(argv)

    CANDIDATE.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(args.generator), str(args.exe),
         "--output", str(CANDIDATE), "--report"],
        text=True,
    )
    if result.returncode:
        return result.returncode

    candidate_rows = _rows(CANDIDATE)
    tracked_rows = _rows(TRACKED) if TRACKED.is_file() else []
    if candidate_rows == tracked_rows:
        print(f"[relocs] exact: {len(candidate_rows) - 1} sites; "
              f"tracked sha256 {_digest(TRACKED)}")
        return 0
    print(f"[relocs] drift: generated {len(candidate_rows) - 1} sites, "
          f"tracked {max(0, len(tracked_rows) - 1)}", file=sys.stderr)
    if not args.write:
        print("[relocs] inspect build/gen/relocs.tsv; pass --write to admit it",
              file=sys.stderr)
        return 1
    TRACKED.write_bytes(CANDIDATE.read_bytes())
    print(f"[relocs] wrote {TRACKED.relative_to(REPO)}; sha256 {_digest(TRACKED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
