"""Resolve the exact VC5 servicing payload from executable-native witnesses.

The PE linker stamp is a hard rejection gate.  Surviving candidates are then
compared using relocation-masked exact static-library member matches over all
4,384 FPO extents.  The tracked matrix may name a preferred candidate to test
first; its complete tool panel, compatible linker, and non-empty exact archive
panel must all pass before selection.  The fallback is acquired only if that
preferred payload fails.
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


def matrix_policy() -> dict:
    data = tomllib.loads(MATRIX.read_text())
    return {key: data[key] for key in
            ("selection_policy", "preferred_candidate", "fallback_candidate")
            if key in data}


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


def _numeric_prefix(version: str) -> tuple[int, int] | None:
    try:
        fields = version.split(".")
        return int(fields[0]), int(fields[1])
    except (IndexError, ValueError):
        return None


def _aggregate(hashes) -> str:
    return hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest()


def census(args, matrix: list[dict], tools: list[dict[str, str]],
           archives: list[dict[str, str]]) -> tuple[list[dict], str | None]:
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
            missing_roles = [role for role in ROLES
                             if not tool_by[(candidate["id"], role)]["path"]]
            tool_set = _aggregate(
                tool_by[(candidate["id"], role)]["sha256"] for role in ROLES)
            archive_set = _aggregate(
                row["sha256"] for row in archives
                if row["candidate"] == candidate["id"])
            if stamp_compatible and missing_roles:
                state = "INCOMPLETE-PAYLOAD"
            elif (stamp_compatible and
                  _numeric_prefix(actual_link) != (link_major, link_minor)):
                state = "REJECTED-ACTUAL-LINKER"
            elif (stamp_compatible and candidate.get("expected_tool_set_sha256")
                  and tool_set != candidate["expected_tool_set_sha256"]):
                state = "REJECTED-TOOL-SET"
            elif (stamp_compatible and candidate.get("expected_archive_set_sha256")
                  and archive_set != candidate["expected_archive_set_sha256"]):
                state = "REJECTED-ARCHIVE-SET"
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

    policy = matrix_policy()
    preferred = policy.get("preferred_candidate")
    preferred_row = next((row for row in summaries
                          if row["candidate"] == preferred), None)
    if preferred_row is not None:
        if (preferred_row["state"] == "CANDIDATE" and
                int(preferred_row["library_unique_fpo"]) > 0):
            preferred_row["state"] = "PREFERRED-PASS"
            preferred_row["evidence"] = (
                f'{policy.get("selection_policy", "preferred-first")}; '
                f'PE linker stamp; {preferred_row["library_unique_fpo"]} '
                "bijective exact FPO archive witnesses")
            selected = preferred
        else:
            preferred_row["evidence"] = (
                preferred_row["evidence"] or
                f'{policy.get("selection_policy", "preferred-first")} failed; '
                f'acquire {policy.get("fallback_candidate", "fallback")}'
            )
            selected = None
    else:
        survivors = [row for row in summaries
                     if row["state"] != "REJECTED-LINKER"]
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


def write_selection(selected: str, summaries: list[dict], archives: list[dict],
                    tools: list[dict]) -> None:
    row = next(row for row in summaries if row["candidate"] == selected)
    hashes = [item["sha256"] for item in archives if item["candidate"] == selected]
    tool_hashes = [item["sha256"] for item in tools
                   if item["candidate"] == selected and item["sha256"]]
    policy = matrix_policy()
    selection_policy = policy.get("selection_policy", "matrix")
    SELECTION.write_text(
        'status = "selected"\n'
        f'candidate = "{selected}"\n'
        f'service_level = "{row["service_level"]}"\n'
        f'selection_policy = "{selection_policy}"\n'
        f'fallback_candidate = "{policy.get("fallback_candidate", "")}"\n'
        f'target_pe_linker = "{row["target_pe_linker"]}"\n'
        f'linker_file_version = "{row["actual_link"]}"\n'
        f'tool_set_sha256 = "{_aggregate(tool_hashes)}"\n'
        f'archive_set_sha256 = "{_aggregate(hashes)}"\n'
        f'evidence = "{row["evidence"]}"\n')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=retail_exe())
    parser.add_argument("--fpo", type=Path, default=RETAIL / "functions_fpo.tsv")
    parser.add_argument("--relocs", type=Path, default=RETAIL / "relocs.tsv")
    parser.add_argument("--candidate", action="append", default=[], metavar="ID=PATH")
    parser.add_argument("--write", action="store_true",
                        help="commit the preferred candidate only after its exact panel passes")
    parser.add_argument("--write-evidence", action="store_true",
                        help="refresh the tracked diagnostic matrix (does not select a compiler)")
    args = parser.parse_args(argv)
    try:
        matrix = candidates(args.candidate)
    except ValueError as error:
        parser.error(str(error))
    tools = tool_rows(matrix)
    archives = archive_rows(matrix)
    summary, selected = census(args, matrix, tools, archives)
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
            write_selection(selected, summary, archives, tools)
            print(f"[compiler-census] wrote {SELECTION.relative_to(REPO)}")
        return 0
    policy = matrix_policy()
    if policy.get("preferred_candidate"):
        print(f"[compiler-census] unresolved: {policy['preferred_candidate']} failed; "
              f"acquire {policy.get('fallback_candidate', 'the fallback')}")
    else:
        print("[compiler-census] unresolved: complete surviving payload matrix "
              "is required for a servicing-level decision")
    return 1 if args.write else 0


if __name__ == "__main__":
    raise SystemExit(main())
