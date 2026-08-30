"""Exact-RVA ratchet for the manually maintained serde candidate wall."""

from __future__ import annotations

import argparse
from pathlib import Path

from rom1.core.paths import RETAIL
from rom1.core.tsv import read as read_tsv
from rom1.sema.serde import REPORT, Candidate, discover, write_report

WALL = RETAIL / "serde_candidates.tsv"
SCHEMA = ["rva", "signals", "status", "note"]
STATUSES = {"target", "reconstructed", "static-library"}


def load_wall(path: Path = WALL) -> list[dict[str, str]]:
    _banner, fields, rows = read_tsv(path)
    if fields != SCHEMA:
        raise ValueError(f"{path}: expected schema {SCHEMA}, got {fields}")
    return rows


def expected_status(candidate: Candidate) -> str:
    if candidate.channel in {"src", "src_compgen"}:
        return "reconstructed"
    if candidate.channel in {"functions_static_libs", "functions_zlib"}:
        return "static-library"
    return "target"


def compare(candidates: dict[int, Candidate], rows: list[dict[str, str]]) -> list[str]:
    findings: list[str] = []
    wall: dict[int, dict[str, str]] = {}
    for row in rows:
        try:
            rva = int(row["rva"], 0)
        except ValueError:
            findings.append(f"invalid wall RVA {row['rva']!r}")
            continue
        if rva in wall:
            findings.append(f"duplicate wall RVA 0x{rva:06x}")
            continue
        wall[rva] = row
        if row["status"] not in STATUSES:
            findings.append(f"0x{rva:06x}: invalid status {row['status']!r}")

    for rva in sorted(candidates.keys() - wall.keys()):
        findings.append(f"0x{rva:06x}: NEW candidate missing from manual wall "
                        f"({candidates[rva].signal_text()})")
    for rva in sorted(wall.keys() - candidates.keys()):
        findings.append(f"0x{rva:06x}: wall candidate disappeared from retail "
                        "discovery; investigate, never silently drop it")
    for rva in sorted(candidates.keys() & wall.keys()):
        actual = candidates[rva]
        saved = {signal for signal in wall[rva]["signals"].split(",") if signal}
        if saved != actual.signals:
            findings.append(
                f"0x{rva:06x}: signals changed "
                f"{','.join(sorted(saved)) or '-'} -> {actual.signal_text() or '-'}")
        want = expected_status(actual)
        if wall[rva]["status"] != want:
            findings.append(f"0x{rva:06x}: status {wall[rva]['status']} should be "
                            f"{want} for channel {actual.channel or 'unclaimed'}")
    return findings


def gate_findings() -> list[str]:
    candidates = discover()
    write_report(candidates)
    return compare(candidates, load_wall())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 verify serde-coverage",
                                 description=__doc__)
    ap.parse_args(argv)
    candidates = discover()
    write_report(candidates)
    findings = compare(candidates, load_wall())
    if findings:
        print(f"serde coverage: FAIL ({len(findings)} finding(s))")
        print("\n".join(f"  {row}" for row in findings))
        return 1
    print(f"serde coverage: OK ({len(candidates)} exact-RVA candidates; "
          f"report {REPORT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
