"""Relocation-masked census of retail FPO functions against VC5 archives.

The report is evidence, not a name oracle: every ambiguity remains visible and
only a bijective exact extent/byte match is eligible for ``--write`` promotion.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import struct
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from rom1.core.paths import BUILD, REPO, RETAIL, retail_exe
from rom1.core.pe import Pe


OUTPUT = BUILD / "gen/library_census.tsv"
PROVIDERS = RETAIL / "functions_static_libs.tsv"
FPO = RETAIL / "functions_fpo.tsv"
RELOCS = RETAIL / "relocs.tsv"
COMPILER = REPO / "config/compiler.toml"
MSVC_ARCHIVES = (
    "LIBCMT.LIB", "LIBCIMT.LIB", "LIBCPMT.LIB", "OLDNAMES.LIB",
    "NAFXCW.LIB", "MFC42.LIB", "MSVCPRT.LIB",
)
DX_ARCHIVES = ("dxguid.lib", "ddraw.lib", "dsound.lib")
I386 = 0x14C
FUNCTION_TYPE = 0x20
EXECUTE = 0x20000000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mask_bytes(payload: bytes, sites: set[int]) -> bytes:
    out = bytearray(payload)
    for site in sites:
        if 0 <= site < len(out):
            out[site:min(site + 4, len(out))] = bytes(
                min(4, len(out) - site))
    return bytes(out)


def trim_padding(payload: bytes) -> bytes:
    end = len(payload)
    while end > 1 and payload[end - 1] in (0x90, 0xCC):
        end -= 1
    return payload[:end]


def archive_members(data: bytes):
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("not a COFF archive")
    longnames = b""
    offset = 8
    while offset + 60 <= len(data):
        header = data[offset:offset + 60]
        if header[58:60] != b"`\n":
            raise ValueError(f"bad archive member at {offset:#x}")
        size = int(header[48:58].decode("ascii").strip())
        name = header[:16].decode("latin-1").rstrip()
        start = offset + 60
        payload = data[start:start + size]
        if name == "//":
            longnames = payload
        elif name not in ("/", ""):
            if name.startswith("/") and name[1:].isdigit():
                begin = int(name[1:])
                stops = [x for x in (longnames.find(b"\0", begin),
                                     longnames.find(b"\n", begin)) if x >= 0]
                end = min(stops) if stops else len(longnames)
                name = longnames[begin:end].decode("latin-1").rstrip("/")
            else:
                name = name.rstrip("/")
            yield name.replace("\\", "/"), payload
        offset = start + size + (size & 1)


@dataclass(frozen=True)
class Candidate:
    archive: str
    archive_hash: str
    member: str
    member_hash: str
    symbol: str
    order: int
    payload: bytes
    reloc_sites: frozenset[int]


def _coff_name(raw: bytes, data: bytes, strtab: int) -> str:
    if raw[:4] == b"\0\0\0\0":
        offset = strtab + struct.unpack_from("<I", raw, 4)[0]
        end = data.find(b"\0", offset)
        return data[offset:end].decode("latin-1")
    if raw.startswith(b"/") and raw[1:].rstrip(b"\0").isdigit():
        offset = strtab + int(raw[1:].rstrip(b"\0"))
        end = data.find(b"\0", offset)
        return data[offset:end].decode("latin-1")
    return raw.rstrip(b"\0").decode("latin-1")


def coff_functions(data: bytes, *, archive: str, archive_hash: str,
                   member: str) -> list[Candidate]:
    if len(data) < 20:
        return []
    machine, nsec, _stamp, symptr, nsym, optsz, _flags = struct.unpack_from(
        "<HHIIIHH", data, 0)
    if machine != I386 or not symptr or not nsym:
        return []
    strtab = symptr + nsym * 18
    if strtab + 4 > len(data):
        return []
    sections = []
    for index in range(nsec):
        base = 20 + optsz + index * 40
        if base + 40 > len(data):
            return []
        name = _coff_name(data[base:base + 8], data, strtab)
        raw_size, raw_ptr, reloc_ptr = struct.unpack_from("<III", data, base + 16)
        reloc_count = struct.unpack_from("<H", data, base + 32)[0]
        chars = struct.unpack_from("<I", data, base + 36)[0]
        relocs = set()
        for slot in range(reloc_count):
            entry = reloc_ptr + slot * 10
            if entry + 10 <= len(data):
                relocs.add(struct.unpack_from("<I", data, entry)[0])
        sections.append((name, raw_size, raw_ptr, chars, relocs))

    symbols: dict[int, list[tuple[int, str]]] = defaultdict(list)
    index = 0
    while index < nsym:
        base = symptr + index * 18
        if base + 18 > len(data):
            break
        name = _coff_name(data[base:base + 8], data, strtab)
        value, section, typ, storage, aux = struct.unpack_from("<IhHBB", data, base + 8)
        if (typ == FUNCTION_TYPE and storage in (2, 3)
                and 1 <= section <= len(sections)
                and sections[section - 1][3] & EXECUTE):
            symbols[section].append((value, name))
        index += 1 + aux

    rows: list[Candidate] = []
    order = 0
    member_hash = sha256(data)
    for section_index, definitions in sorted(symbols.items()):
        _name, raw_size, raw_ptr, _chars, relocs = sections[section_index - 1]
        definitions.sort()
        for slot, (start, symbol) in enumerate(definitions):
            end = definitions[slot + 1][0] if slot + 1 < len(definitions) else raw_size
            if end <= start or raw_ptr + end > len(data):
                continue
            payload = trim_padding(data[raw_ptr + start:raw_ptr + end])
            local_relocs = frozenset(site - start for site in relocs
                                     if start <= site < start + len(payload))
            rows.append(Candidate(archive, archive_hash, member, member_hash,
                                  symbol, order, payload, local_relocs))
            order += 1
    return rows


def load_fpo(path: Path) -> list[dict]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(
            (line for line in stream if not line.lstrip().startswith("#")),
            delimiter="\t" if path.suffix == ".tsv" else ","))
    result = []
    for row in rows:
        result.append({"rva": int(row["rva"], 0), "size": int(row["size"], 0),
                       "has_seh": int(row.get("has_seh", "0"))})
    return result


def load_relocs(path: Path) -> set[int]:
    rows = set()
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or line == "site_rva\tkind":
            continue
        rva, kind = line.split("\t")
        if kind != "dir32":
            raise ValueError(f"{path}: unsupported relocation kind {kind!r}")
        value = int(rva, 0)
        if value in rows:
            raise ValueError(f"{path}: duplicate relocation {value:#x}")
        rows.add(value)
    return rows


def default_archives(toolchain: Path) -> list[Path]:
    roots = (toolchain / "msvc/lib", toolchain / "dx/Lib")
    wanted = {name.lower() for name in MSVC_ARCHIVES + DX_ARCHIVES}
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        found.extend(path for path in root.iterdir()
                     if path.is_file() and path.name.lower() in wanted)
    return sorted(found, key=lambda p: p.name.lower())


def match_confidence(candidate_count: int, reverse_count: int) -> tuple[str, str]:
    """Classify an exact byte match without mistaking a generic body for ID.

    A forward-unique match is insufficient: ``mov eax,<reloc>; ret`` may name
    one archive symbol yet occur at hundreds of retail extents. Promotion
    requires the relation to be one-to-one in both directions.
    """
    if candidate_count == 0:
        return "", ""
    if candidate_count == 1 and reverse_count == 1:
        return "HIGH", "bijective union-reloc-mask exact extent"
    if candidate_count == 1:
        return ("AMBIG", f"non-discriminating candidate matches "
                f"{reverse_count} retail extents")
    return "AMBIG", "collision retained"


def scan(exe: Path, fpo: Path, relocs: Path,
         archives: list[Path]) -> list[dict[str, str]]:
    pe = Pe(exe)
    retail_relocs = load_relocs(relocs)
    buckets: dict[int, list[Candidate]] = defaultdict(list)
    for archive_path in archives:
        archive_data = archive_path.read_bytes()
        archive_hash = sha256(archive_data)
        for member, payload in archive_members(archive_data):
            for candidate in coff_functions(
                    payload, archive=archive_path.name,
                    archive_hash=archive_hash, member=member):
                buckets[len(candidate.payload)].append(candidate)

    exe_hash = sha256(exe.read_bytes())
    probes = []
    for function in load_fpo(fpo):
        rva, declared_size = function["rva"], function["size"]
        payload = pe.read(rva, declared_size)
        if payload is None:
            continue
        payload = trim_padding(payload)
        retail_sites = {site - rva for site in retail_relocs
                        if rva <= site < rva + len(payload)}
        matches = []
        for candidate in buckets.get(len(payload), ()):
            union = retail_sites | set(candidate.reloc_sites)
            if mask_bytes(payload, union) == mask_bytes(candidate.payload, union):
                matches.append(candidate)
        matches.sort(key=lambda c: (c.archive.lower(), c.member, c.order, c.symbol))
        probes.append((function, payload, retail_sites, matches))

    reverse_hits = Counter(candidate for _function, _payload, _sites, matches
                           in probes for candidate in matches)
    output = []
    for function, payload, retail_sites, matches in probes:
        rva = function["rva"]
        primary = matches[0] if matches else None
        reverse_count = reverse_hits[primary] if primary is not None else 0
        confidence, evidence = match_confidence(len(matches), reverse_count)
        output.append({
            "rva": f"0x{rva:x}",
            "size": f"0x{len(payload):x}",
            "class": "library-exact" if matches else "unknown",
            "confidence": confidence,
            "library": primary.archive if primary else "",
            "member": primary.member if primary else "",
            "symbol": primary.symbol if primary else "",
            "candidates": str(len(matches)),
            "retail_sha256": exe_hash,
            "archive_sha256": primary.archive_hash if primary else "",
            "member_sha256": primary.member_hash if primary else "",
            "masked_sha256": sha256(mask_bytes(payload, retail_sites)),
            "evidence": evidence,
        })
    return output


HEADER = ("rva", "size", "class", "confidence", "library", "member",
          "symbol", "candidates", "retail_sha256", "archive_sha256",
          "member_sha256", "masked_sha256", "evidence")


def write_report(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADER, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def promote(rows: list[dict[str, str]], path: Path) -> int:
    manual = []
    if path.is_file():
        manual = [line for line in path.read_text().splitlines()
                  if line and not line.startswith("#")
                  and not line.startswith("rva\t")
                  and "\tlibrary-census:" not in line]
    generated = []
    for row in rows:
        if row["confidence"] != "HIGH":
            continue
        source = (f"library-census:{row['archive_sha256'][:12]}:"
                  f"{row['member']}:{row['member_sha256'][:12]}")
        generated.append("\t".join((row["rva"], row["symbol"], row["library"],
                                     "HIGH", source)))
    merged = sorted(set(manual + generated), key=lambda line: int(line.split("\t", 1)[0], 0))
    path.write_text(
        "# Bijective exact static-library function providers. Generated rows are\n"
        "# replaced only by `rom1 tool library-census --write`; manual rows survive.\n"
        "rva\tname\tlib\tconfidence\tsource\n"
        + "".join(line + "\n" for line in merged))
    return len(generated)


def selected_toolchain(archives: list[Path]) -> str:
    """Return the selected candidate id, refusing an unproven archive set."""
    config = tomllib.loads(COMPILER.read_text()) if COMPILER.is_file() else {}
    if config.get("status") != "selected":
        raise ValueError("compiler servicing level is unresolved; run the complete "
                         "`rom1 tool compiler-census --write` matrix first")
    hashes = sorted(sha256(path.read_bytes()) for path in archives)
    actual = hashlib.sha256("".join(hashes).encode()).hexdigest()
    if actual != config.get("archive_set_sha256"):
        raise ValueError("archive set does not match config/compiler.toml")
    return str(config["candidate"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=retail_exe())
    parser.add_argument("--fpo", type=Path, default=FPO)
    parser.add_argument("--relocs", type=Path, default=RELOCS)
    parser.add_argument("--toolchain", type=Path,
                        default=Path(os.environ.get("ROM1_TOOLCHAIN", "")))
    parser.add_argument("--archive", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    archives = args.archive or default_archives(args.toolchain)
    if not archives:
        parser.error("no archives found; set ROM1_TOOLCHAIN or pass --archive")
    rows = scan(args.exe, args.fpo, args.relocs, archives)
    write_report(rows, args.output)
    exact = sum(row["confidence"] == "HIGH" for row in rows)
    ambiguous = sum(row["confidence"] == "AMBIG" for row in rows)
    print(f"[library-census] {len(rows)} FPO functions, {exact} bijective exact, "
          f"{ambiguous} ambiguous; {args.output.relative_to(REPO) if args.output.is_relative_to(REPO) else args.output}")
    if args.write:
        try:
            candidate = selected_toolchain(archives)
        except ValueError as error:
            parser.error(str(error))
        print(f"[library-census] promoted {promote(rows, PROVIDERS)} HIGH rows "
              f"from selected {candidate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
