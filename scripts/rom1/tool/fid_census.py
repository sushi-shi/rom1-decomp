"""Gruntz-style masked COFF FID census over the full manual function list.

This complements ``library-census`` (the conservative 4,384-FPO panel) with
the two scans used by Gruntz:

* anchored matching at every manually admitted function start;
* a strict off-start sweep at padding transitions/exact-function ends.

Relocation operands are wildcarded on both sides.  HIGH requires a substantial
signature, a unique archive identity, a unique retail RVA, and an exact extent
(FPO/structural, or a signature followed only by linker padding up to the next
manual start). Candidate archives can be classified in the collision universe
of a control archive set, so a generic third-party wrapper cannot masquerade as
a unique match merely because the CRT was omitted from the scan. Provider
promotion is fail-closed unless the active toolchain's complete archive set
matches the hash-selected compiler in ``compiler.toml``.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path

from rom1.core.paths import BUILD, RETAIL, retail_exe
from rom1.core.pe import Pe
from rom1.core.relocs import load as load_relocs
from rom1.core.tsv import read as read_tsv, write as write_tsv
from rom1.tool import library_census


OUTPUT = BUILD / "gen/fid_census.tsv"
OFFSTART = BUILD / "gen/fid_offstart.tsv"
PROVIDERS = RETAIL / "functions_static_libs.tsv"
MIN_LEN = 8
MIN_FIXED = 6
HIGH_LEN = 16
HIGH_FIXED = 10
OFFSTART_LEN = 24
OFFSTART_FIXED = 16
PAD = {0x90, 0xCC}


def _identity(candidate) -> tuple[str, str, str, int]:
    return (candidate.archive, candidate.member, candidate.symbol, candidate.order)


def _fixed(candidate) -> tuple[int, ...]:
    masked = set()
    for site in candidate.reloc_sites:
        masked.update(range(site, min(site + 4, len(candidate.payload))))
    return tuple(index for index in range(len(candidate.payload)) if index not in masked)


def signatures(archives: list[Path]):
    result = []
    for archive_path in archives:
        data = archive_path.read_bytes()
        archive_hash = library_census.sha256(data)
        for member, payload in library_census.archive_members(data):
            for candidate in library_census.coff_functions(
                    payload, archive=archive_path.name,
                    archive_hash=archive_hash, member=member):
                fixed = _fixed(candidate)
                if len(candidate.payload) >= MIN_LEN and len(fixed) >= MIN_FIXED:
                    result.append((candidate, fixed))
    result.sort(key=lambda item: (len(item[0].payload), _identity(item[0])))
    return result


def _manual_rows(pe: Pe) -> list[dict]:
    _banner, fields, raw = read_tsv(RETAIL / "functions.tsv")
    if fields != ["rva", "kind"]:
        raise ValueError("functions.tsv must have rva<TAB>kind")
    rows = [{"rva": int(row["rva"], 0), "kind": row["kind"]} for row in raw]
    if [row["rva"] for row in rows] != sorted({row["rva"] for row in rows}):
        raise ValueError("functions.tsv starts must be unique and sorted")
    _banner, _fields, exact_raw = read_tsv(RETAIL / "function_extents.tsv")
    exact = {int(row["rva"], 0): int(row["size"], 0) for row in exact_raw}
    starts = [row["rva"] for row in rows]
    orphan = sorted(set(exact) - set(starts))
    if orphan:
        raise ValueError(f"function_extents.tsv has orphan {orphan[0]:#x}")
    text_end = pe.text_span()[1]
    for index, row in enumerate(rows):
        row["room"] = (starts[index + 1] if index + 1 < len(starts) else text_end) \
            - row["rva"]
        row["exact"] = row["rva"] in exact
        row["size"] = exact.get(row["rva"], row["room"])
        if row["size"] > row["room"]:
            raise ValueError(f"exact extent at {row['rva']:#x} crosses next start")
    return rows


def _matches(pe: Pe, rva: int, candidate, fixed: tuple[int, ...],
             reloc_sites: list[int]) -> bool:
    body = pe.read(rva, len(candidate.payload))
    if body is None:
        return False
    retail_masked = set()
    begin_site = bisect.bisect_left(reloc_sites, rva)
    end_site = bisect.bisect_left(reloc_sites, rva + len(candidate.payload))
    for site in reloc_sites[begin_site:end_site]:
        begin = site - rva
        retail_masked.update(range(begin, min(begin + 4, len(candidate.payload))))
    return all(body[index] == candidate.payload[index]
               for index in fixed if index not in retail_masked)


def _padding_after(pe: Pe, rva: int, length: int, room: int) -> bool:
    if length > room:
        return False
    suffix = pe.read(rva + length, room - length)
    return suffix is not None and all(byte in PAD for byte in suffix)


def anchored(pe: Pe, prepared, reloc_sites: list[int], functions: list[dict]):
    by_len = defaultdict(list)
    for candidate, fixed in prepared:
        by_len[len(candidate.payload)].append((candidate, fixed))
    probes = []
    for function in functions:
        if function["kind"] in ("eh", "pad", "thunk"):
            continue
        rva, room = function["rva"], function["room"]
        extent = function["size"] if function["exact"] else room
        raw = pe.read(rva, extent)
        if raw is None:
            continue
        # A manual start owns the bytes up to its exact structural edge, or to
        # the next manual start.  Like Gruntz, trim only terminal linker fill:
        # this gives one admissible extent instead of trying every shorter
        # archive signature against the same body.
        usable = len(library_census.trim_padding(raw))
        candidate_lengths = (usable,)
        hits = []
        for length in candidate_lengths:
            if length not in by_len:
                continue
            for candidate, fixed in by_len[length]:
                if _matches(pe, rva, candidate, fixed, reloc_sites):
                    hits.append((candidate, fixed, length))
        if hits:
            probes.append((function, hits))
    return probes


def _classify(probes, location_key="rva", include_identities=None,
              all_matches: bool = False):
    identity_rvas = defaultdict(set)
    rva_identities = defaultdict(set)
    for function, hits in probes:
        location = function[location_key]
        for candidate, _fixed_bytes, _length in hits:
            identity_rvas[_identity(candidate)].add(location)
            rva_identities[location].add(_identity(candidate))
    rows = []
    for function, hits in probes:
        rva = function[location_key]

        eligible = [item for item in hits
                    if include_identities is None
                    or _identity(item[0]) in include_identities]
        if not eligible:
            continue

        def key(item):
            candidate, fixed, length = item
            unique = len(identity_rvas[_identity(candidate)]) == 1
            return (not unique, -length, -len(fixed), _identity(candidate))

        selected = sorted(eligible, key=key)
        if not all_matches:
            selected = selected[:1]
        seen = set()
        for candidate, fixed, length in selected:
            identity = _identity(candidate)
            if identity in seen:
                continue
            seen.add(identity)
            reverse = len(identity_rvas[identity])
            names = len(rva_identities[rva])
            substantial = length >= HIGH_LEN and len(fixed) >= HIGH_FIXED
            ambiguous = reverse > 1 or names > 1
            if not ambiguous and substantial:
                confidence = "HIGH"
            elif not ambiguous:
                confidence = "MEDIUM"
            elif substantial:
                confidence = "AMBIG"
            else:
                confidence = "LOW"
            notes = []
            if reverse > 1:
                notes.append(f"identity_multimatch={reverse}")
            if names > 1:
                notes.append(f"rva_multiidentity={names}")
            if length < HIGH_LEN:
                notes.append(f"short={length}")
            if len(fixed) < HIGH_FIXED:
                notes.append(f"fewfixed={len(fixed)}")
            rows.append({
                "rva": f"0x{rva:06x}", "name": candidate.symbol,
                "lib": candidate.archive, "confidence": confidence,
                "extent": f"0x{length:x}", "fixed_bytes": str(len(fixed)),
                "identity_match_count": str(reverse),
                "rva_identity_count": str(names),
                "member": candidate.member,
                "archive_sha256": candidate.archive_hash,
                "member_sha256": candidate.member_hash,
                "source": function.get("source", "anchored"),
                "notes": ";".join(notes) if notes else "-",
            })
    rows.sort(key=lambda row: (int(row["rva"], 0), row["lib"], row["member"],
                               row["name"]))
    return rows


def offstart(pe: Pe, prepared, reloc_sites: list[int], known_rows: list[dict]):
    text_lo, text_hi = pe.text_span()
    text = pe.read(text_lo, text_hi - text_lo)
    if text is None:
        raise ValueError("cannot read .text")
    known = {row["rva"] for row in known_rows}
    exact_intervals = sorted((row["rva"], row["rva"] + row["size"])
                             for row in known_rows if row["exact"])
    exact_starts = [lo for lo, _hi in exact_intervals]

    def inside_exact(rva: int) -> bool:
        index = bisect.bisect_right(exact_starts, rva) - 1
        return index >= 0 and exact_intervals[index][0] < rva < exact_intervals[index][1]

    boundaries = {text_lo}
    boundaries.update(text_lo + index for index in range(1, len(text))
                      if text[index - 1] in PAD and text[index] not in PAD)
    boundaries.update(hi for _lo, hi in exact_intervals if hi < text_hi)
    boundaries.difference_update(known)
    boundaries = {rva for rva in boundaries if not inside_exact(rva)}
    known_starts = sorted(known)
    by_first = defaultdict(lambda: defaultdict(list))
    for candidate, fixed in prepared:
        if len(candidate.payload) < OFFSTART_LEN or len(fixed) < OFFSTART_FIXED:
            continue
        by_first[fixed[0]][candidate.payload[fixed[0]]].append((candidate, fixed))
    probes = []
    for rva in sorted(boundaries):
        room_end_index = bisect.bisect_right(known_starts, rva)
        room_end = (known_starts[room_end_index]
                    if room_end_index < len(known_starts) else text_hi)
        hits = []
        for first, values in sorted(by_first.items()):
            byte = pe.read(rva + first, 1)
            if byte is None:
                continue
            for candidate, fixed in values.get(byte[0], ()):
                length = len(candidate.payload)
                if rva + length > room_end:
                    continue
                if not _padding_after(pe, rva, length, room_end - rva):
                    continue
                if _matches(pe, rva, candidate, fixed, reloc_sites):
                    hits.append((candidate, fixed, length))
        if hits:
            probes.append(({"rva": rva, "source": "offstart-padding-boundary"}, hits))
    return probes


FIELDS = ["rva", "name", "lib", "confidence", "extent", "fixed_bytes",
          "identity_match_count", "rva_identity_count", "member",
          "archive_sha256", "member_sha256", "source", "notes"]


def write_report(path: Path, rows: list[dict[str, str]], banner=None):
    write_tsv(path, banner or [], FIELDS, rows)


def promote(rows: list[dict[str, str]], path: Path) -> int:
    existing = []
    if path.is_file():
        _banner, _fields, old = read_tsv(path)
        existing = [row for row in old if not row.get("source", "").startswith("fid-census:")]
    generated = []
    for row in rows:
        if row["confidence"] != "HIGH":
            continue
        generated.append({
            "rva": row["rva"], "name": row["name"], "lib": row["lib"],
            "confidence": "HIGH",
            "source": (f"fid-census:{row['archive_sha256'][:12]}:"
                       f"{row['member']}:{row['member_sha256'][:12]}"),
        })
    merged = sorted(existing + generated, key=lambda row: int(row["rva"], 0))
    write_tsv(path, ["# Selected-toolchain, globally unique masked COFF providers."],
              ["rva", "name", "lib", "confidence", "source"], merged)
    return len(generated)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=retail_exe())
    parser.add_argument("--toolchain", type=Path,
                        default=Path(os.environ.get("ROM1_TOOLCHAIN", "")))
    parser.add_argument("--archive", action="append", type=Path, default=[])
    parser.add_argument("--control-archive", action="append", type=Path, default=[],
                        help="extra archives used only to expose signature collisions")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--offstart-output", type=Path, default=OFFSTART)
    parser.add_argument("--all-output", type=Path,
                        help="write every candidate identity per anchored RVA")
    parser.add_argument("--write-evidence", type=Path,
                        help="also write the anchored report to a tracked evidence path")
    parser.add_argument("--write", action="store_true",
                        help="promote HIGH rows; requires selected exact toolchain")
    args = parser.parse_args(argv)
    archives = args.archive or library_census.default_archives(args.toolchain)
    if not archives:
        parser.error("no archives found; set ROM1_TOOLCHAIN or pass --archive")
    pe = Pe(args.exe)
    prepared = signatures(archives)
    controls = signatures(args.control_archive)
    universe = prepared + controls
    included = {_identity(candidate) for candidate, _fixed in prepared}
    reloc_sites = load_relocs()
    known_rows = _manual_rows(pe)
    anchored_probes = anchored(pe, universe, reloc_sites, known_rows)
    offstart_probes = offstart(pe, universe, reloc_sites, known_rows)
    anchored_rows = _classify(anchored_probes, include_identities=included)
    off_rows = _classify(offstart_probes, include_identities=included)
    exe_sha = hashlib.sha256(pe.data).hexdigest()
    archive_set = hashlib.sha256("".join(sorted(
        hashlib.sha256(path.read_bytes()).hexdigest() for path in archives)).encode()).hexdigest()
    banner = [
        f"# retail_sha256={exe_sha}",
        f"# archive_set_sha256={archive_set}",
        f"# signatures={len(prepared)} control_signatures={len(controls)} "
        f"manual_starts={len(known_rows)} "
        f"min_len={MIN_LEN} min_fixed={MIN_FIXED} high_len={HIGH_LEN} "
        f"high_fixed={HIGH_FIXED}",
        f"# offstart_min_len={OFFSTART_LEN} offstart_min_fixed={OFFSTART_FIXED}",
    ]
    write_report(args.output, anchored_rows, banner)
    write_report(args.offstart_output, off_rows, banner)
    if args.all_output:
        write_report(args.all_output, _classify(
            anchored_probes, include_identities=included, all_matches=True), banner)
    if args.write_evidence:
        write_report(args.write_evidence, anchored_rows, banner)
    tiers = Counter(row["confidence"] for row in anchored_rows)
    libs = Counter(row["lib"] for row in anchored_rows if row["confidence"] == "HIGH")
    print(f"[fid-census] {len(prepared)} usable signatures + "
          f"{len(controls)} controls; "
          f"{len(anchored_rows)} anchored RVAs {dict(tiers)}; "
          f"{len(off_rows)} off-start RVAs; HIGH by library {dict(libs)}")
    if args.write:
        try:
            candidate = library_census.selected_toolchain(archives)
        except ValueError as error:
            parser.error(str(error))
        print(f"[fid-census] {candidate}: promoted "
              f"{promote(anchored_rows + off_rows, PROVIDERS)} HIGH rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
