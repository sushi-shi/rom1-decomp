"""Regenerate executable-native PE, section, import, FPO and string evidence.

Both channels are read directly from the pinned retail PE.  The FPO table is
lossless: no frame record is collapsed to a mere function start.  String rows
retain file offset and RVA so the extraction is independently auditable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import struct
from pathlib import Path

from rom1.core.paths import REPO, RETAIL, retail_exe
from rom1.core.pe import Pe


FPO = RETAIL / "functions_fpo.tsv"
STRINGS = RETAIL / "strings.tsv"
SECTIONS = RETAIL / "sections.tsv"
IMPORTS = RETAIL / "imports.tsv"
DEBUG = RETAIL / "debug.tsv"
PE_FACTS = RETAIL / "pe.tsv"
FRAME = {0: "FPO", 1: "TRAP", 2: "TSS", 3: "NONFPO"}
DEBUG_DIRECTORY = 6
DEBUG_FPO = 3


def debug_entries(pe: Pe):
    if len(pe.directories) <= DEBUG_DIRECTORY:
        return
    rva, size = pe.directories[DEBUG_DIRECTORY]
    offset = pe.rva_to_offset(rva)
    if offset is None:
        raise ValueError(f"debug directory RVA 0x{rva:x} has no file offset")
    for pos in range(offset, offset + size, 28):
        if pos + 28 > len(pe.data):
            raise ValueError("truncated IMAGE_DEBUG_DIRECTORY")
        yield struct.unpack_from("<IIHHIIII", pe.data, pos)


def fpo_rows(pe: Pe) -> list[dict[str, str]]:
    rows = []
    for _chars, _stamp, _maj, _min, kind, size, _rva, pointer in debug_entries(pe):
        if kind != DEBUG_FPO:
            continue
        raw = pe.data[pointer:pointer + size]
        if len(raw) != size or size % 16:
            raise ValueError("malformed IMAGE_DEBUG_TYPE_FPO payload")
        for pos in range(0, size, 16):
            rva, extent, locals_size = struct.unpack_from("<III", raw, pos)
            params_words, flags = struct.unpack_from("<HH", raw, pos + 12)
            rows.append({
                "rva": f"0x{rva:06x}", "size": f"0x{extent:x}",
                "local_dwords": f"0x{locals_size:x}",
                "local_bytes": f"0x{locals_size * 4:x}",
                "param_dwords": f"0x{params_words:x}",
                "param_bytes": f"0x{params_words * 4:x}",
                "prolog_bytes": f"0x{flags & 0xff:x}",
                "saved_regs": str((flags >> 8) & 7),
                "frame": FRAME[(flags >> 14) & 3],
                "use_bp": str((flags >> 12) & 1),
                "has_seh": str((flags >> 11) & 1),
                "reserved": str((flags >> 13) & 1),
                "flags_raw": f"0x{flags:04x}",
            })
    rows.sort(key=lambda row: int(row["rva"], 0))
    if len({row["rva"] for row in rows}) != len(rows):
        raise ValueError("duplicate FPO function RVA")
    return rows


def _runs(data: bytes, wide: bool = False):
    step = 2 if wide else 1
    pos = 0
    while pos < len(data):
        begin = pos
        chars = []
        while pos + step <= len(data):
            value = data[pos]
            if wide and data[pos + 1] != 0:
                break
            if value != 9 and not 0x20 <= value <= 0x7e:
                break
            chars.append(chr(value))
            pos += step
        if len(chars) >= 4:
            yield begin, pos - begin, "".join(chars)
        pos = max(pos + step, begin + step)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\t", "\\t") \
        .replace("\r", "\\r").replace("\n", "\\n")


def string_rows(pe: Pe) -> list[dict[str, str]]:
    rows = []
    for encoding, wide in (("ascii", False), ("utf16le", True)):
        for offset, byte_length, value in _runs(pe.data, wide):
            mapped = pe.offset_to_rva(offset)
            if mapped is None:
                continue
            rva, section = mapped
            rows.append({
                "rva": f"0x{rva:06x}", "file_offset": f"0x{offset:x}",
                "section": section, "encoding": encoding,
                "byte_length": f"0x{byte_length:x}", "text": _escape(value),
            })
    rows.sort(key=lambda row: (int(row["rva"], 0), row["encoding"], row["text"]))
    return rows


def section_rows(pe: Pe) -> list[dict[str, str]]:
    return [{"order": str(index), "name": section["name"],
             "rva": f"0x{section['va']:06x}",
             "virtual_size": f"0x{section['vsize']:x}",
             "raw_size": f"0x{section['rsize']:x}",
             "file_offset": f"0x{section['rptr']:x}",
             "characteristics": f"0x{section['characteristics']:08x}"}
            for index, section in enumerate(pe.sections)]


def import_rows(pe: Pe) -> list[dict[str, str]]:
    """Lossless descriptor/thunk order, hint, name and decorated spelling."""
    if len(pe.directories) <= 1 or not pe.directories[1][0]:
        return []

    def raw(rva: int) -> int:
        offset = pe.rva_to_offset(rva)
        if offset is None:
            raise ValueError(f"import RVA 0x{rva:x} has no file offset")
        return offset

    def cstr(offset: int) -> str:
        return pe.data[offset:pe.data.index(0, offset)].decode("ascii", "replace")

    rows = []
    pos = raw(pe.directories[1][0])
    descriptor = 0
    while True:
        lookup, stamp, forward, name_rva, iat_rva = struct.unpack_from(
            "<IIIII", pe.data, pos)
        if not any((lookup, stamp, forward, name_rva, iat_rva)):
            break
        dll = cstr(raw(name_rva))
        thunk = raw(lookup or iat_rva)
        index = 0
        while True:
            value = struct.unpack_from("<I", pe.data, thunk + index * 4)[0]
            if not value:
                break
            ordinal = value & 0xffff if value & 0x80000000 else None
            hint = ""
            name = ""
            if ordinal is None:
                name_offset = raw(value)
                hint = str(struct.unpack_from("<H", pe.data, name_offset)[0])
                name = cstr(name_offset + 2)
            rows.append({"descriptor_order": str(descriptor), "dll": dll,
                         "thunk_order": str(index),
                         "iat_rva": f"0x{iat_rva + index * 4:06x}",
                         "kind": "ordinal" if ordinal is not None else "name",
                         "name": name,
                         "ordinal": "" if ordinal is None else str(ordinal),
                         "hint": hint,
                         "descriptor_timestamp": f"0x{stamp:08x}",
                         "forwarder_chain": f"0x{forward:08x}"})
            index += 1
        descriptor += 1
        pos += 20
    return rows


def debug_rows(pe: Pe) -> list[dict[str, str]]:
    rows = []
    for index, (_chars, stamp, major, minor, kind, size, rva, pointer) in \
            enumerate(debug_entries(pe)):
        detail = ""
        payload = pe.data[pointer:pointer + size]
        if kind == 2 and payload.startswith(b"NB10") and len(payload) >= 16:
            _signature, offset, cv_stamp, age = struct.unpack_from("<4sIII", payload)
            pdb = payload[16:].split(b"\0", 1)[0].decode("latin1", "replace")
            detail = (f"signature=NB10;offset=0x{offset:x};"
                      f"timestamp=0x{cv_stamp:08x};age={age};pdb={pdb}")
        elif kind == DEBUG_FPO:
            detail = f"records={size // 16}"
        rows.append({"order": str(index), "type": str(kind),
                     "timestamp": f"0x{stamp:08x}",
                     "version": f"{major}.{minor}", "size": str(size),
                     "rva": f"0x{rva:06x}", "file_offset": f"0x{pointer:x}",
                     "detail": detail})
    return rows


def pe_fact_rows(pe: Pe, sha: str) -> list[dict[str, str]]:
    d, opt = pe.data, pe.optional_offset
    coff = pe.pe_offset + 4
    values = (
        ("sha256", sha), ("file_size", str(len(d))),
        ("machine", f"0x{struct.unpack_from('<H', d, coff)[0]:04x}"),
        ("coff_timestamp", f"0x{struct.unpack_from('<I', d, coff + 4)[0]:08x}"),
        ("linker_version", f"{pe.linker_version[0]}.{pe.linker_version[1]:02d}"),
        ("image_base", f"0x{pe.image_base:08x}"),
        ("entry_rva", f"0x{struct.unpack_from('<I', d, opt + 16)[0]:06x}"),
        ("section_alignment", f"0x{struct.unpack_from('<I', d, opt + 32)[0]:x}"),
        ("file_alignment", f"0x{struct.unpack_from('<I', d, opt + 36)[0]:x}"),
        ("image_size", f"0x{struct.unpack_from('<I', d, opt + 56)[0]:x}"),
        ("subsystem", str(struct.unpack_from('<H', d, opt + 68)[0])),
        ("reloc_directory_rva", f"0x{pe.directories[5][0]:x}"),
        ("reloc_directory_size", f"0x{pe.directories[5][1]:x}"),
    )
    return [{"key": key, "value": value, "authority": "retail PE"}
            for key, value in values]


def _render(rows: list[dict[str, str]], fields: tuple[str, ...], sha: str) -> str:
    from io import StringIO
    out = StringIO()
    out.write(f"# retail_sha256={sha}\n")
    writer = csv.DictWriter(out, fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _check_or_write(path: Path, payload: str, write: bool) -> bool:
    if path.is_file() and path.read_text() == payload:
        print(f"[retail-census] exact {path.relative_to(REPO)}")
        return True
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload)
        print(f"[retail-census] wrote {path.relative_to(REPO)}")
        return True
    print(f"[retail-census] DRIFT {path.relative_to(REPO)}")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=retail_exe())
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    pe = Pe(args.exe)
    sha = hashlib.sha256(pe.data).hexdigest()
    fpo = fpo_rows(pe)
    strings = string_rows(pe)
    sections = section_rows(pe)
    imports = import_rows(pe)
    debug = debug_rows(pe)
    checks = (
        _check_or_write(FPO, _render(fpo, ("rva", "size", "local_dwords",
            "local_bytes", "param_dwords", "param_bytes", "prolog_bytes",
            "saved_regs", "frame", "use_bp", "has_seh", "reserved",
            "flags_raw"), sha), args.write),
        _check_or_write(STRINGS, _render(strings, ("rva", "file_offset", "section",
            "encoding", "byte_length", "text"), sha), args.write),
        _check_or_write(SECTIONS, _render(sections, ("order", "name", "rva",
            "virtual_size", "raw_size", "file_offset", "characteristics"), sha),
            args.write),
        _check_or_write(IMPORTS, _render(imports, ("descriptor_order", "dll",
            "thunk_order", "iat_rva", "kind", "name", "ordinal", "hint",
            "descriptor_timestamp", "forwarder_chain"), sha), args.write),
        _check_or_write(DEBUG, _render(debug, ("order", "type", "timestamp",
            "version", "size", "rva", "file_offset", "detail"), sha), args.write),
        _check_or_write(PE_FACTS, _render(pe_fact_rows(pe, sha),
            ("key", "value", "authority"), sha), args.write),
    )
    print(f"[retail-census] {len(fpo)} FPO records, {len(strings)} strings, "
          f"{len(imports)} imports, {len(sections)} sections")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
