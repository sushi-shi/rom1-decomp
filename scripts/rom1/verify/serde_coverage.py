"""Exact-RVA ratchet for the manually maintained serde candidate wall."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from rom1.core.paths import CONFIG, RETAIL
from rom1.core.tsv import read as read_tsv, rint
from rom1.sema.serde import REPORT, Candidate, discover, write_report

WALL = RETAIL / "serde_candidates.tsv"
FID_CENSUS = CONFIG / "evidence/vc5-sp2-fid-census.tsv"
COMPILER = CONFIG / "compiler.toml"
SCHEMA = ["rva", "signals", "status", "note"]
STATUSES = {"target", "reconstructed", "static-library"}
VENDOR_COLLISION_LIBRARIES = {"NAFXCW.LIB"}


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


def load_selected_vendor_collisions(
    fid_path: Path = FID_CENSUS,
    compiler_path: Path = COMPILER,
) -> set[int]:
    """Return unpromotable-but-vendor-owned SP2 FID collisions.

    These rows remain absent from ``functions_static_libs.tsv`` because their
    exact bytes do not identify one unique symbol.  The shared vendor archive
    and multi-identity evidence are nevertheless enough to keep them out of
    game-source reconstruction.  Fail closed if the census is not for the
    selected archive payload.
    """
    selection = tomllib.loads(compiler_path.read_text())
    if selection.get("status") != "selected":
        return set()
    archive_hash = selection.get("archive_set_sha256", "")
    banner, fields, rows = read_tsv(fid_path)
    evidence_hash = next(
        (line.split("=", 1)[1] for line in banner
         if line.startswith("# archive_set_sha256=")),
        "",
    )
    if not archive_hash or evidence_hash != archive_hash:
        raise ValueError(
            f"{fid_path}: archive-set hash {evidence_hash or '<missing>'} "
            f"does not match selected {archive_hash or '<missing>'}"
        )
    required = {
        "rva", "lib", "confidence", "rva_identity_count", "source", "notes",
    }
    missing = required - set(fields)
    if missing:
        raise ValueError(f"{fid_path}: missing fields {sorted(missing)}")

    collisions: set[int] = set()
    for row in rows:
        if row["lib"] not in VENDOR_COLLISION_LIBRARIES:
            continue
        if row["confidence"] != "AMBIG" or row["source"] != "anchored":
            continue
        count = rint(row["rva_identity_count"])
        if count <= 1 or f"rva_multiidentity={count}" not in row["notes"]:
            continue
        collisions.add(rint(row["rva"]))
    return collisions


def compare(
    candidates: dict[int, Candidate],
    rows: list[dict[str, str]],
    vendor_collisions: set[int] | None = None,
) -> list[str]:
    findings: list[str] = []
    vendor_collisions = vendor_collisions or set()
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
        if want == "target" and rva in vendor_collisions:
            want = "static-library"
        if wall[rva]["status"] != want:
            findings.append(f"0x{rva:06x}: status {wall[rva]['status']} should be "
                            f"{want} for channel {actual.channel or 'unclaimed'}")
    return findings


def gate_findings() -> list[str]:
    candidates = discover()
    write_report(candidates)
    return compare(candidates, load_wall(), load_selected_vendor_collisions())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 verify serde-coverage",
                                 description=__doc__)
    ap.parse_args(argv)
    candidates = discover()
    write_report(candidates)
    findings = compare(candidates, load_wall(), load_selected_vendor_collisions())
    if findings:
        print(f"serde coverage: FAIL ({len(findings)} finding(s))")
        print("\n".join(f"  {row}" for row in findings))
        return 1
    print(f"serde coverage: OK ({len(candidates)} exact-RVA candidates; "
          f"report {REPORT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
