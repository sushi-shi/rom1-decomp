"""Resolve the exact VC5 servicing payload from executable-native witnesses.

The PE linker stamp is a hard rejection gate.  Surviving candidates are then
compared using relocation-masked exact static-library member matches over all
4,384 FPO extents.  No candidate is selected until every surviving servicing
level is present and at least one byte witness discriminates the winner.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import struct
import tomllib
from pathlib import Path

from rom1.core.paths import BUILD, CONFIG, REPO, RETAIL, retail_exe
from rom1.core.pe import Pe
from rom1.tool import library_census


MATRIX = CONFIG / "toolchains.toml"
SELECTION = CONFIG / "compiler.toml"
SUMMARY = BUILD / "gen/compiler_census.tsv"
TOOLS = BUILD / "gen/compiler_tools.tsv"
ARCHIVES = BUILD / "gen/compiler_archives.tsv"
EVIDENCE = CONFIG / "evidence"
ROLES = ("cl.exe", "c1.dll", "c1xx.dll", "c2.exe", "link.exe",
         "cvtres.exe", "mspdb50.dll")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_ci(root: Path, name: str) -> Path | None:
    if not root.is_dir():
        return None
    wanted = name.lower()
    return next((path for path in root.iterdir()
                 if path.is_file() and path.name.lower() == wanted), None)


def fixed_file_version(path: Path) -> str:
    """Read VS_FIXEDFILEINFO without depending on host PE packages."""
    data = path.read_bytes()
    signature = struct.pack("<I", 0xFEEF04BD)
    offset = data.find(signature)
    if offset < 0 or offset + 16 > len(data):
        return ""
    _sig, _struct, ms, ls = struct.unpack_from("<IIII", data, offset)
    parts = (ms >> 16, ms & 0xffff, ls >> 16, ls & 0xffff)
    while len(parts) > 2 and parts[-1] == 0:
        parts = parts[:-1]
    return ".".join(map(str, parts))


def candidates(overrides: list[str]) -> list[dict]:
    configured = tomllib.loads(MATRIX.read_text())["candidate"]
    roots = {}
    for item in overrides:
        key, sep, value = item.partition("=")
        if not sep or not key or not value:
            raise ValueError(f"expected ID=PATH, got {item!r}")
        roots[key] = Path(value)
    result = []
    for row in configured:
        root = roots.get(row["id"])
        if root is None and os.environ.get(row["env"]):
            root = Path(os.environ[row["env"]])
        if root is None and row.get("bootstrap_env") and os.environ.get(row["bootstrap_env"]):
            root = Path(os.environ[row["bootstrap_env"]])
        result.append({**row, "root": root})
    unknown = set(roots) - {row["id"] for row in configured}
    if unknown:
        raise ValueError("unknown candidate id(s): " + ", ".join(sorted(unknown)))
    return result


def tool_rows(matrix: list[dict]) -> list[dict[str, str]]:
    rows = []
    for candidate in matrix:
        root = candidate["root"]
        for role in ROLES:
            path = find_ci(root / "msvc/bin", role) if root else None
            rows.append({
                "candidate": candidate["id"],
                "service_level": candidate["service_level"],
                "role": role,
                "path": str(path.relative_to(root)) if path and root else "",
                "size": str(path.stat().st_size) if path else "",
                "version": fixed_file_version(path) if path else "",
                "sha256": sha256(path) if path else "",
            })
    return rows


def archive_rows(matrix: list[dict]) -> list[dict[str, str]]:
    rows = []
    for candidate in matrix:
        root = candidate["root"]
        if not root:
            continue
        for path in library_census.default_archives(root):
            rows.append({"candidate": candidate["id"],
                         "service_level": candidate["service_level"],
                         "archive": path.name, "size": str(path.stat().st_size),
                         "sha256": sha256(path)})
    return rows


def _write(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _prefix(version: str) -> str:
    fields = version.split(".")
    return ".".join(fields[:2]) if len(fields) >= 2 else version


def census(args, matrix: list[dict], tools: list[dict[str, str]]) -> tuple[list[dict], str | None]:
    link_major, link_minor = Pe(args.exe).linker_version
    target_link = f"{link_major}.{link_minor:02d}"
    tool_by = {(row["candidate"], row["role"].lower()): row for row in tools}
    reports: dict[str, list[dict[str, str]]] = {}
    summaries = []
    for candidate in matrix:
        root = candidate["root"]
        actual_link = tool_by[(candidate["id"], "link.exe")]["version"]
        expected = candidate["expected_link"]
        stamp_compatible = _prefix(expected) == target_link
        state = "CANDIDATE" if stamp_compatible else "REJECTED-LINKER"
        exact = ambiguous = matched = 0
        if root:
            report = library_census.scan(args.exe, args.fpo, args.relocs,
                                          library_census.default_archives(root))
            reports[candidate["id"]] = report
            exact = sum(row["confidence"] == "HIGH" for row in report)
            ambiguous = sum(row["confidence"] == "AMBIG" for row in report)
            matched = exact + ambiguous
        elif stamp_compatible:
            state = "MISSING-PAYLOAD"
        summaries.append({
            "candidate": candidate["id"],
            "service_level": candidate["service_level"],
            "target_pe_linker": target_link,
            "expected_link": expected,
            "actual_link": actual_link,
            "payload": "present" if root else "missing",
            "library_matched_fpo": str(matched),
            "library_unique_fpo": str(exact),
            "library_colliding_fpo": str(ambiguous),
            "exclusive_fpo": "0",
            "state": state,
            "evidence": "PE linker stamp" if not stamp_compatible else "",
        })

    survivors = [row for row in summaries if row["state"] != "REJECTED-LINKER"]
    present = [row for row in survivors if row["payload"] == "present"]
    if len(present) >= 2 and len(present) == len(survivors):
        hitsets = {key: {row["rva"] for row in report if row["confidence"]}
                   for key, report in reports.items()}
        for summary in present:
            mine = hitsets[summary["candidate"]]
            others = set().union(*(hits for key, hits in hitsets.items()
                                   if key != summary["candidate"]))
            summary["exclusive_fpo"] = str(len(mine - others))
        winners = [row for row in present if int(row["exclusive_fpo"]) > 0
                   and int(row["library_matched_fpo"]) == max(
                       int(other["library_matched_fpo"]) for other in present)]
        selected = winners[0]["candidate"] if len(winners) == 1 else None
    else:
        selected = None
    return summaries, selected


def write_selection(selected: str, summaries: list[dict], archives: list[dict]) -> None:
    row = next(row for row in summaries if row["candidate"] == selected)
    hashes = sorted(item["sha256"] for item in archives if item["candidate"] == selected)
    SELECTION.write_text(
        'status = "selected"\n'
        f'candidate = "{selected}"\n'
        f'service_level = "{row["service_level"]}"\n'
        f'target_pe_linker = "{row["target_pe_linker"]}"\n'
        f'linker_file_version = "{row["actual_link"]}"\n'
        f'archive_set_sha256 = "{hashlib.sha256("".join(hashes).encode()).hexdigest()}"\n'
        f'evidence = "complete servicing matrix plus {row["exclusive_fpo"]} exclusive exact FPO archive witnesses"\n')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=retail_exe())
    parser.add_argument("--fpo", type=Path, default=RETAIL / "functions_fpo.tsv")
    parser.add_argument("--relocs", type=Path, default=RETAIL / "relocs.tsv")
    parser.add_argument("--candidate", action="append", default=[], metavar="ID=PATH")
    parser.add_argument("--write", action="store_true",
                        help="commit a selection only after the complete matrix discriminates it")
    parser.add_argument("--write-evidence", action="store_true",
                        help="refresh the tracked diagnostic matrix (does not select a compiler)")
    args = parser.parse_args(argv)
    try:
        matrix = candidates(args.candidate)
    except ValueError as error:
        parser.error(str(error))
    tools = tool_rows(matrix)
    archives = archive_rows(matrix)
    summary, selected = census(args, matrix, tools)
    _write(TOOLS, ("candidate", "service_level", "role", "path", "size",
                   "version", "sha256"), tools)
    _write(ARCHIVES, ("candidate", "service_level", "archive", "size", "sha256"), archives)
    _write(SUMMARY, ("candidate", "service_level", "target_pe_linker",
          "expected_link", "actual_link", "payload", "library_matched_fpo",
          "library_unique_fpo", "library_colliding_fpo", "exclusive_fpo",
          "state", "evidence"), summary)
    if args.write_evidence:
        _write(EVIDENCE / "compiler_tools.tsv", ("candidate", "service_level",
               "role", "path", "size", "version", "sha256"), tools)
        _write(EVIDENCE / "compiler_archives.tsv", ("candidate", "service_level",
               "archive", "size", "sha256"), archives)
        _write(EVIDENCE / "compiler_census.tsv", ("candidate", "service_level",
               "target_pe_linker", "expected_link", "actual_link", "payload",
               "library_matched_fpo", "library_unique_fpo",
               "library_colliding_fpo", "exclusive_fpo", "state", "evidence"),
               summary)
        print(f"[compiler-census] wrote {EVIDENCE.relative_to(REPO)}/")
    for row in summary:
        print(f"[compiler-census] {row['candidate']:8} {row['state']:15} "
              f"link={row['actual_link'] or row['expected_link']} "
              f"library={row['library_matched_fpo']}")
    if selected:
        print(f"[compiler-census] selected {selected}")
        if args.write:
            write_selection(selected, summary, archives)
            print(f"[compiler-census] wrote {SELECTION.relative_to(REPO)}")
        return 0
    print("[compiler-census] unresolved: both SP1 and SP2 payloads are required "
          "for a servicing-level decision")
    return 1 if args.write else 0


if __name__ == "__main__":
    raise SystemExit(main())
