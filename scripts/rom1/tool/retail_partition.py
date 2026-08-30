"""Recover the retail code/data partition beyond the PE's FPO subset.

The shipped FPO stream is the authority for 4,384 function extents, but it is
not a complete function table.  This generator combines those exact records
with a pinned analyzer-start census and derives the compiler/linker structures
that the executable itself describes:

* every VC5 ``/GX`` registration stub, FuncInfo and unwind/catch action;
* the terminal EH contribution band and its exact function starts;
* the ``.CRT$XI``/``.CRT$XC`` tables called by ``_cinit``;
* compiler-generated C++ dynamic initializers and pure IAT jump-thunk bands;
* MFC ``CRuntimeClass`` records and vtables named by GetRuntimeClass slots.

Analyzer sizes are retained as evidence only.  Exact extents are emitted to
separate tables and always outrank the analyzer in the Model census.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import struct
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rom1.core.paths import REPO, RETAIL, retail_exe
from rom1.core.pe import Pe
from rom1.core.relocs import load as load_relocs
from rom1.core.tsv import read as read_tsv, write as write_tsv
from rom1.tool.retail_census import fpo_rows, import_rows, string_rows


DISASM = RETAIL / "functions_disasm.tsv"
FUNCTIONS = RETAIL / "functions.tsv"
FUNCTION_EXTENTS = RETAIL / "function_extents.tsv"
EH_GROUPS = RETAIL / "eh_groups.tsv"
EH_ACTIONS = RETAIL / "eh_actions.tsv"
DYNINIT = RETAIL / "dyninit.tsv"
THUNKS = RETAIL / "thunks.tsv"
RUNTIME_CLASSES = RETAIL / "runtime_classes.tsv"
VTABLES = RETAIL / "vtables.tsv"
DATA = RETAIL / "data.tsv"
DATA_EXTENTS = RETAIL / "data_extents.tsv"
DATA_VTABLES = RETAIL / "data_vtables.tsv"
DATA_STATIC_LIBS = RETAIL / "data_static_libs.tsv"
LINK_BANDS = RETAIL / "link_bands.tsv"
PARTITION_SUMMARY = RETAIL / "partition_summary.tsv"

FUNCINFO_MAGIC = 0x19930520
FUNCINFO_SIZE = 32
UNWIND_ENTRY_SIZE = 8
TRY_ENTRY_SIZE = 20
HANDLER_ENTRY_SIZE = 16
EH_STUB_SIZE = 10


def _sha(pe: Pe) -> str:
    return hashlib.sha256(pe.data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:06x}"


def _number(value) -> int:
    return int(value, 0) if isinstance(value, str) else int(value or 0)


def _va_to_rva(pe: Pe, value: int) -> int:
    return value - pe.image_base if value >= pe.image_base else value


def _u32(pe: Pe, rva: int) -> int | None:
    raw = pe.read(rva, 4)
    return None if raw is None else struct.unpack_from("<I", raw)[0]


def _section_for(pe: Pe, rva: int) -> dict | None:
    return next((section for section in pe.sections
                 if section["va"] <= rva < section["va"]
                 + max(section["vsize"], section["rsize"])), None)


def _stored_dwords(pe: Pe, names=(".rdata", ".data")):
    for name in names:
        section = pe.section(name)
        for offset in range(0, section["rsize"] - 3, 4):
            rva = section["va"] + offset
            yield rva, struct.unpack_from(
                "<I", pe.data, section["rptr"] + offset)[0]


def load_fpo(pe: Pe) -> dict[int, int]:
    return {int(row["rva"], 0): int(row["size"], 0)
            for row in fpo_rows(pe)}


def load_disasm(path: Path, pe: Pe) -> list[dict[str, str]]:
    """Normalize a radare2 ``aflj`` TSV.  Its extents remain diagnostic."""
    with path.open(newline="") as stream:
        raw = list(csv.DictReader(
            (line for line in stream if not line.lstrip().startswith("#")),
            delimiter="\t"))
    text_lo, text_hi = pe.text_span()
    out = []
    for row in raw:
        address = row.get("addr") or row.get("rva")
        if address is None:
            raise ValueError(f"{path}: analyzer table needs addr or rva")
        rva = _va_to_rva(pe, int(address, 0))
        if not text_lo <= rva < text_hi:
            continue
        out.append({
            "rva": _hex(rva),
            "size": f"0x{_number(row.get('size') or 0):x}",
            "real_size": f"0x{_number(row.get('realsz') or row.get('real_size')
                                       or row.get('size') or 0):x}",
            "instructions": str(_number(row.get("ninstrs")
                                         or row.get("instructions") or 0)),
            "name": row.get("name", ""),
            "source": "radare2 -AA/aflj; start evidence only",
        })
    out.sort(key=lambda row: int(row["rva"], 0))
    if len({row["rva"] for row in out}) != len(out):
        raise ValueError(f"{path}: duplicate analyzer function start")
    return out


@dataclass(frozen=True)
class EhGroup:
    stub: int
    handler: int
    funcinfo: int
    states: int
    unwind_map: int
    tries: int
    try_map: int
    ip_entries: int
    ip_map: int
    actions: tuple[tuple[int, str, int], ...]
    handler_arrays: tuple[tuple[int, int], ...]
    owner_sites: tuple[int, ...]


def _parse_funcinfo(pe: Pe, funcinfo: int):
    raw = pe.read(funcinfo, 28)
    if raw is None:
        return None
    magic, states, unwind_va, tries, try_va, ip_entries, ip_va = \
        struct.unpack_from("<IiIiIiI", raw)
    if (magic != FUNCINFO_MAGIC or states < 0 or states > 0x1000
            or tries < 0 or tries > 0x1000 or ip_entries < 0):
        return None
    unwind = _va_to_rva(pe, unwind_va) if unwind_va else 0
    try_map = _va_to_rva(pe, try_va) if try_va else 0
    ip_map = _va_to_rva(pe, ip_va) if ip_va else 0
    actions: list[tuple[int, str, int]] = []
    if states:
        table = pe.read(unwind, states * UNWIND_ENTRY_SIZE)
        if table is None:
            return None
        for index in range(states):
            _to_state, action_va = struct.unpack_from("<iI", table,
                                                       index * UNWIND_ENTRY_SIZE)
            if action_va:
                actions.append((_va_to_rva(pe, action_va), "unwind", index))
    handler_arrays = []
    for index in range(tries):
        block = pe.read(try_map + index * TRY_ENTRY_SIZE, TRY_ENTRY_SIZE)
        if block is None:
            return None
        _low, _high, _catch_high, catches, handler_va = struct.unpack_from(
            "<iiiiI", block)
        if catches < 0 or catches > 0x1000:
            return None
        handler_array = _va_to_rva(pe, handler_va) if handler_va else 0
        handler_arrays.append((handler_array, catches))
        table = pe.read(handler_array, catches * HANDLER_ENTRY_SIZE)
        if table is None:
            return None
        for slot in range(catches):
            _adjectives, _type, _disp, handler = struct.unpack_from(
                "<IIiI", table, slot * HANDLER_ENTRY_SIZE)
            if handler:
                actions.append((_va_to_rva(pe, handler), "catch",
                                index * 0x10000 + slot))
    return (states, unwind, tries, try_map, ip_entries, ip_map,
            tuple(actions), tuple(handler_arrays))


def recover_eh(pe: Pe, reloc_sites: set[int]) -> tuple[list[EhGroup], int]:
    text_lo, text_hi = pe.text_span()
    text = pe.read(text_lo, text_hi - text_lo)
    if text is None:
        raise ValueError("cannot read virtual .text")
    owner_by_stub: dict[int, list[int]] = defaultdict(list)
    for site in sorted(reloc_sites):
        value = _u32(pe, site)
        if value is not None:
            owner_by_stub[_va_to_rva(pe, value)].append(site)
    groups = []
    for offset in range(0, len(text) - EH_STUB_SIZE + 1):
        if text[offset] != 0xB8 or text[offset + 5] != 0xE9:
            continue
        stub = text_lo + offset
        funcinfo = _va_to_rva(pe, struct.unpack_from("<I", text, offset + 1)[0])
        parsed = _parse_funcinfo(pe, funcinfo)
        if parsed is None:
            continue
        target = stub + EH_STUB_SIZE + struct.unpack_from("<i", text, offset + 6)[0]
        states, unwind, tries, try_map, ip_entries, ip_map, actions, arrays = parsed
        if not text_lo <= target < text_hi:
            continue
        if any(not text_lo <= action < text_hi for action, _kind, _slot in actions):
            continue
        groups.append(EhGroup(stub, target, funcinfo, states, unwind, tries,
                              try_map, ip_entries, ip_map, actions, arrays,
                              tuple(owner_by_stub.get(stub, ()))))
    groups.sort(key=lambda group: group.stub)
    if len({group.stub for group in groups}) != len(groups):
        raise ValueError("duplicate EH registration stub")
    handlers = {group.handler for group in groups}
    if len(handlers) != 1:
        raise ValueError(f"EH stubs target {len(handlers)} frame handlers")
    return groups, next(iter(handlers))


def eh_tables(groups: list[EhGroup], fpo: dict[int, int], text_hi: int):
    fpo_end = max(rva + size for rva, size in fpo.items())
    actions = sorted({action for group in groups for action, _kind, _slot
                      in group.actions if fpo_end <= action < text_hi})
    if not actions:
        raise ValueError("no terminal EH action band")
    tail = actions[0]
    rows = []
    for group in groups:
        tail_actions = sorted({action for action, _kind, _slot in group.actions
                               if tail <= action < text_hi})
        rows.append({
            "stub_rva": _hex(group.stub), "stub_size": f"0x{EH_STUB_SIZE:x}",
            "frame_handler_rva": _hex(group.handler),
            "funcinfo_rva": _hex(group.funcinfo),
            "max_state": str(group.states), "unwind_map_rva": _hex(group.unwind_map),
            "try_blocks": str(group.tries), "try_map_rva": _hex(group.try_map),
            "ip_map_entries": str(group.ip_entries), "ip_map_rva": _hex(group.ip_map),
            "action_refs": str(len(group.actions)),
            "unique_actions": str(len({a for a, _k, _s in group.actions})),
            "tail_actions": str(len(tail_actions)),
            "owner_ref_sites": ";".join(_hex(site) for site in group.owner_sites),
            "evidence": "mov eax,FuncInfo; jmp shared __CxxFrameHandler",
        })
    by_action: dict[int, list[tuple[EhGroup, str, int]]] = defaultdict(list)
    for group in groups:
        for action, kind, slot in group.actions:
            by_action[action].append((group, kind, slot))
    action_rows = []
    for action, refs in sorted(by_action.items()):
        kinds = sorted({kind for _group, kind, _slot in refs})
        action_rows.append({
            "action_rva": _hex(action),
            "region": "tail" if action >= tail else "body",
            "roles": ";".join(kinds),
            "group_stubs": ";".join(_hex(group.stub) for group, _k, _s in refs),
            "map_slots": ";".join(str(slot) for _group, _kind, slot in refs),
            "references": str(len(refs)),
        })
    partition = set(actions)
    partition.update(group.stub for group in groups
                     if not any(tail <= action < text_hi
                                for action, _kind, _slot in group.actions))
    if min(partition) != tail:
        raise ValueError("EH partition does not begin at the action-band edge")
    if max(group.stub + EH_STUB_SIZE for group in groups) != text_hi:
        raise ValueError("final EH registration stub does not end at virtual .text")
    return rows, action_rows, partition, tail


def find_init_tables(pe: Pe) -> tuple[tuple[int, int], tuple[int, int], int]:
    """Return ``(XI, XC, _initterm)`` from `_cinit`'s two call sequences."""
    text_lo, text_hi = pe.text_span()
    text = pe.read(text_lo, text_hi - text_lo)
    if text is None:
        raise ValueError("cannot read .text")
    found = []
    for off in range(0, len(text) - 36):
        if not (text[off] == 0x68 and text[off + 5] == 0x68
                and text[off + 10] == 0xE8
                and text[off + 15:off + 18] == b"\x83\xc4\x08"
                and text[off + 18] == 0x68 and text[off + 23] == 0x68
                and text[off + 28] == 0xE8
                and text[off + 33:off + 36] == b"\x83\xc4\x08"):
            continue
        ends = [struct.unpack_from("<I", text, off + p)[0]
                for p in (1, 19)]
        starts = [struct.unpack_from("<I", text, off + p)[0]
                  for p in (6, 24)]
        calls = [text_lo + off + p + 5 + struct.unpack_from("<i", text, off + p + 1)[0]
                 for p in (10, 28)]
        spans = [(_va_to_rva(pe, start), _va_to_rva(pe, end))
                 for start, end in zip(starts, ends)]
        if calls[0] != calls[1]:
            continue
        if not all(start <= end and (end - start) % 4 == 0
                   and _section_for(pe, start) is not None for start, end in spans):
            continue
        if not all(all((value := _u32(pe, slot)) is not None
                       and (value == 0 or text_lo <= _va_to_rva(pe, value) < text_hi)
                       for slot in range(start, end, 4)) for start, end in spans):
            continue
        found.append((spans, calls[0]))
    if not found:
        raise ValueError("no _initterm table sequence found")
    # `_doexit` carries the same two-call shape for the much smaller XP/XT
    # terminator tables.  `_cinit` is uniquely the sequence with the greatest
    # combined table extent (XC is 136 slots in this image).
    found.sort(key=lambda item: sum(hi - lo for lo, hi in item[0]), reverse=True)
    if (len(found) > 1 and sum(hi - lo for lo, hi in found[0][0])
            == sum(hi - lo for lo, hi in found[1][0])):
        raise ValueError("ambiguous largest _initterm table sequence")
    spans, initterm = found[0]
    spans.sort(key=lambda span: span[1] - span[0])
    return spans[0], spans[1], initterm


def _wrapper_size(pe: Pe, rva: int) -> int | None:
    raw = pe.read(rva, 24)
    if raw is None or not raw.startswith(b"\x55\x8b\xec\xe8"):
        return None
    for size in (10, 15):
        if raw[size - 2:size] == b"\x5d\xc3":
            return size
    return None


def recover_dyninit(pe: Pe, fpo: dict[int, int]):
    xi, xc, initterm = find_init_tables(pe)
    rows = []
    helpers: dict[int, tuple[int, str]] = {}
    for table, span in (("XI", xi), ("XC", xc)):
        for slot in range(span[0], span[1], 4):
            value = _u32(pe, slot)
            if not value:
                continue
            entry = _va_to_rva(pe, value)
            raw = pe.read(entry, 5)
            if raw is None:
                raise ValueError(f"initializer entry {_hex(entry)} is unreadable")
            target = entry
            role = "direct"
            entry_size = fpo.get(entry)
            evidence = "FPO exact extent"
            if raw[0] == 0xE9:
                target = entry + 5 + struct.unpack_from("<i", raw, 1)[0]
                role, entry_size = "forwarder", 5
                evidence = "five-byte E9 forwarder"
            elif entry_size is None:
                entry_size = _wrapper_size(pe, entry)
                evidence = "recognized framed dynamic-initializer wrapper"
            if entry_size is None:
                raise ValueError(f"initializer {_hex(entry)} has no exact extent")
            target_size = fpo.get(target)
            if target == entry:
                target_size = entry_size
            elif target_size is None:
                raise ValueError(f"initializer target {_hex(target)} has no FPO extent")
            rows.append({
                "table": table, "slot_rva": _hex(slot), "entry_rva": _hex(entry),
                "target_rva": _hex(target), "entry_size": f"0x{entry_size:x}",
                "target_size": f"0x{target_size:x}", "role": role,
                "evidence": evidence,
            })
            if table == "XC":
                helpers[entry] = (entry_size, evidence)
                if target != entry:
                    helpers[target] = (target_size, "FPO target of XC forwarder")
    return rows, helpers, xi, xc, initterm


def recover_iat_thunks(pe: Pe, fpo: dict[int, int]):
    imports = {int(row["iat_rva"], 0): f"{row['dll']}!{row['name'] or '#' + row['ordinal']}"
               for row in import_rows(pe)}
    text_lo, text_hi = pe.text_span()
    raw = pe.read(text_lo, text_hi - text_lo)
    if raw is None:
        raise ValueError("cannot read virtual .text")

    # Most import stubs have no FPO record at all.  Recover every FF 25 whose
    # absolute operand names a retail IAT slot, then reject instructions that
    # occur inside a larger exact FPO body.  A remaining stub is a function
    # only when it has its own six-byte FPO extent or belongs to a contiguous
    # six-byte import-stub band.  The latter is the non-incremental linker's
    # exact layout witness; it also prevents arbitrary in-function FF 25
    # instructions from becoming function starts.
    candidates: list[tuple[int, int]] = []
    fpo_intervals = sorted((rva, rva + size) for rva, size in fpo.items())
    for offset in range(0, len(raw) - 5):
        if raw[offset:offset + 2] != b"\xff\x25":
            continue
        rva = text_lo + offset
        iat = _va_to_rva(pe, struct.unpack_from("<I", raw, offset + 2)[0])
        if iat not in imports:
            continue
        owner = next(((lo, hi) for lo, hi in fpo_intervals if lo <= rva < hi), None)
        if owner is not None and owner[0] != rva:
            continue
        candidates.append((rva, iat))

    runs: list[list[tuple[int, int]]] = []
    for candidate in candidates:
        if runs and candidate[0] == runs[-1][-1][0] + 6:
            runs[-1].append(candidate)
        else:
            runs.append([candidate])

    rows = []
    for run in runs:
        for rva, iat in run:
            exact_fpo = fpo.get(rva) == 6
            if len(run) < 2 and not exact_fpo:
                continue
            evidence = ("exact FPO body ff25 <IAT>" if exact_fpo else
                        f"contiguous ff25 <IAT> stub band ({len(run)} entries, "
                        f"{_hex(run[0][0])}..{_hex(run[-1][0] + 6)})")
            rows.append({"rva": _hex(rva), "size": "0x6", "iat_rva": _hex(iat),
                         "import": imports[iat], "evidence": evidence})
    return rows


def _cstr(pe: Pe, va: int, limit: int = 64) -> str | None:
    rva = _va_to_rva(pe, va)
    offset = pe.rva_to_offset(rva)
    if offset is None:
        return None
    end = pe.data.find(b"\0", offset, min(offset + limit, len(pe.data)))
    if end < 0:
        return None
    raw = pe.data[offset:end]
    if not (2 <= len(raw) <= 48 and (raw[:1].isalpha() or raw[:1] == b"_")
            and all(chr(byte).isalnum() or byte == 0x5f for byte in raw)):
        return None
    return raw.decode("latin-1")


def recover_runtime_classes(pe: Pe):
    text_lo, text_hi = pe.text_span()
    data_sections = {section["name"]: (section["va"], section["va"]
                     + max(section["vsize"], section["rsize"]))
                     for section in pe.sections}

    def in_data_va(value: int) -> bool:
        rva = _va_to_rva(pe, value)
        return any(name in (".rdata", ".data") and lo <= rva < hi
                   for name, (lo, hi) in data_sections.items())

    records = {}
    for rva, name_va in _stored_dwords(pe):
        name = _cstr(pe, name_va)
        raw = pe.read(rva, 24)
        if name is None or raw is None:
            continue
        _name, object_size, schema, create_va, base_va, next_va = struct.unpack(
            "<IiIIII", raw)
        create = _va_to_rva(pe, create_va) if create_va else 0
        base = _va_to_rva(pe, base_va) if base_va else 0
        nxt = _va_to_rva(pe, next_va) if next_va else 0
        if not 1 <= object_size <= 0x40000:
            continue
        if not (schema <= 0xFFFF or schema == 0xFFFFFFFF):
            continue
        if create and not text_lo <= create < text_hi:
            continue
        if base_va and not in_data_va(base_va):
            continue
        if next_va and not in_data_va(next_va):
            continue
        records[rva] = {"class": name, "object_size": object_size,
                        "schema": schema, "create": create, "base": base,
                        "next": nxt, "name_rva": _va_to_rva(pe, name_va)}
    by_rva = records
    rows = []
    for rva, record in sorted(records.items(), key=lambda item: item[1]["class"]):
        base_record = by_rva.get(record["base"])
        base_class = base_record["class"] if base_record else ""
        own = (record["object_size"] - base_record["object_size"]
               if base_record else None)
        rows.append({
            "class": record["class"], "rva": _hex(rva), "size": "0x18",
            "name_rva": _hex(record["name_rva"]),
            "object_size": str(record["object_size"]),
            "own_bytes": "" if own is None else str(own),
            "base_class": base_class, "base_rva": _hex(record["base"]),
            "schema": f"0x{record['schema']:x}",
            "dynamic": "1" if record["create"] else "0",
            "create_rva": _hex(record["create"]), "next_rva": _hex(record["next"]),
        })
    return records, rows


def _getrc_target(pe: Pe, function: int, valid: set[int]) -> int | None:
    raw = pe.read(function, 48)
    if raw is None or b"\xc3" not in raw:
        return None
    end = raw.index(0xC3) + 1
    for offset in range(0, end - 4):
        if raw[offset] == 0xB8:
            candidate = _va_to_rva(pe, struct.unpack_from("<I", raw, offset + 1)[0])
            if candidate in valid:
                return candidate
    return None


def recover_vtables(pe: Pe, records: dict[int, dict]):
    text_lo, text_hi = pe.text_span()
    starts: dict[int, int] = {}
    for slot, value in _stored_dwords(pe):
        function = _va_to_rva(pe, value)
        if not text_lo <= function < text_hi:
            continue
        target = _getrc_target(pe, function, set(records))
        if target is not None:
            starts.setdefault(slot, target)
    ordered = sorted(starts)
    rows = []
    for index, start in enumerate(ordered):
        limit = ordered[index + 1] if index + 1 < len(ordered) else 1 << 32
        methods = []
        slot = start
        while slot < limit:
            value = _u32(pe, slot)
            if value is None:
                break
            method = _va_to_rva(pe, value)
            if not text_lo <= method < text_hi:
                break
            methods.append(method)
            slot += 4
        if len(methods) < 1:
            raise ValueError(f"empty GetRuntimeClass vtable at {_hex(start)}")
        runtime = starts[start]
        rows.append({"vtable_rva": _hex(start), "size": f"0x{len(methods) * 4:x}",
                     "methods": str(len(methods)),
                     "class": records[runtime]["class"],
                     "runtime_class_rva": _hex(runtime), "getrc_slot": "0",
                     "method_rvas": ";".join(_hex(method) for method in methods),
                     "evidence": "slot 0 returns named CRuntimeClass record"})
    best = {}
    for row in rows:
        name = row["class"]
        if name not in best or int(row["methods"]) > int(best[name]["methods"]):
            best[name] = row
    providers = []
    for name, row in sorted(best.items()):
        providers.append({"rva": row["vtable_rva"], "size": row["size"],
                          "name": f"??_7{name}@@6B@", "kind": "primary",
                          "note": "GetRuntimeClass/CRuntimeClass retail proof"})
    return rows, providers


def _add_extent(extents: dict[int, tuple[int, str, str]], rva: int, size: int,
                source: str, evidence: str):
    if not rva or not size:
        return
    old = extents.get(rva)
    value = (size, source, evidence)
    if old is not None and old[0] != size:
        raise ValueError(f"conflicting exact extents at {_hex(rva)}: {old[0]} vs {size}")
    if old is None or value < old:
        extents[rva] = value


def _build_data(pe: Pe, groups: list[EhGroup], dyninit_rows: list[dict[str, str]],
                xi: tuple[int, int], xc: tuple[int, int], records: dict[int, dict],
                scan_vtables: list[dict], reloc_sites: set[int]):
    starts: dict[int, str] = {}
    extents: dict[int, tuple[int, str, str]] = {}
    for section in pe.sections:
        if section["name"] in (".rdata", ".data", ".idata"):
            starts[section["va"]] = ""
    for span, name in ((xi, ".CRT$XI"), (xc, ".CRT$XC")):
        starts[span[0]] = ""
        _add_extent(extents, span[0], span[1] - span[0], name,
                    "bounds passed by retail _cinit to _initterm")
    for group in groups:
        starts[group.funcinfo] = "ehtable"
        _add_extent(extents, group.funcinfo, FUNCINFO_SIZE, "FuncInfo",
                    "VC5 FuncInfo fixed record")
        if group.states:
            starts[group.unwind_map] = "ehtable"
            _add_extent(extents, group.unwind_map, group.states * UNWIND_ENTRY_SIZE,
                        "UnwindMap", "maxState * sizeof(UnwindMapEntry)")
        if group.tries:
            starts[group.try_map] = "ehtable"
            _add_extent(extents, group.try_map, group.tries * TRY_ENTRY_SIZE,
                        "TryBlockMap", "nTryBlocks * sizeof(TryBlockMapEntry)")
        for array, catches in group.handler_arrays:
            if catches:
                starts[array] = "ehtable"
                _add_extent(extents, array, catches * HANDLER_ENTRY_SIZE,
                            "HandlerMap", "nCatches * sizeof(HandlerType)")
    for rva, record in records.items():
        starts[rva] = ""
        _add_extent(extents, rva, 24, "CRuntimeClass",
                    "MFC 4.x six-dword runtime-class record")
        name = record["class"].encode("latin-1") + b"\0"
        if pe.read(record["name_rva"], len(name)) != name:
            raise ValueError(f"runtime class string mismatch for {record['class']}")
        starts[record["name_rva"]] = "string"
        _add_extent(extents, record["name_rva"], len(name), "CRuntimeClass name",
                    "NUL-terminated name referenced by CRuntimeClass")
    for row in scan_vtables:
        rva, size = row["start"], row["size"] * 4
        starts[rva] = "vtable"
        _add_extent(extents, rva, size, "vtable",
                    "relocated text-pointer run split at RTTI and code vptr refs")
    # The full string census is deliberately broad evidence. Promotion to a
    # data start is narrower and executable-native: the candidate must begin
    # in initialized data and an admitted DIR32 site must point to it exactly.
    reloc_targets = {
        _va_to_rva(pe, value)
        for site in reloc_sites
        if (value := _u32(pe, site)) is not None
    }
    for row in string_rows(pe):
        rva = int(row["rva"], 0)
        section = _section_for(pe, rva)
        if (rva in reloc_targets and section is not None
                and section["name"] in (".rdata", ".data")
                and rva < section["va"] + section["rsize"]):
            starts.setdefault(rva, "string")
    data_rows = [{"rva": _hex(rva), "kind": kind} for rva, kind in sorted(starts.items())]
    extent_rows = [{"rva": _hex(rva), "size": f"0x{size:x}", "source": source,
                    "evidence": evidence}
                   for rva, (size, source, evidence) in sorted(extents.items())]
    return data_rows, extent_rows


def generate(pe: Pe, disasm_source: Path):
    sha = _sha(pe)
    fpo = load_fpo(pe)
    disasm = load_disasm(disasm_source, pe)
    reloc_sites = load_relocs(RETAIL / "relocs.tsv")
    groups, frame_handler = recover_eh(pe, reloc_sites)
    text_lo, text_hi = pe.text_span()
    group_rows, action_rows, eh_partition, eh_tail = eh_tables(groups, fpo, text_hi)
    dyninit_rows, helpers, xi, xc, initterm = recover_dyninit(pe, fpo)
    thunk_rows = recover_iat_thunks(pe, fpo)
    runtime_records, runtime_rows = recover_runtime_classes(pe)
    vtable_rows, vtable_providers = recover_vtables(pe, runtime_records)
    # The runtime-class pass names primary MFC views, but a pointer run can
    # also contain ctor-stamped secondary views whose first slot does not
    # return a CRuntimeClass.  The complete image scanner supplies those cuts.
    from rom1.verify.vtable_scan import real_vtables
    scan_vtables = real_vtables()
    scan_by_start = {row["start"]: row for row in scan_vtables}
    for row in vtable_rows:
        rva = int(row["vtable_rva"], 0)
        scanned = scan_by_start.get(rva)
        if scanned is None:
            row["evidence"] += "; runtime proof compensates for absent relocation site"
            continue
        row["size"] = f"0x{scanned['size'] * 4:x}"
        row["methods"] = str(scanned["size"])
        row["method_rvas"] = ";".join(
            row["method_rvas"].split(";")[:scanned["size"]])
        row["evidence"] += "; exact end from RTTI/code-ref split census"
    for row in vtable_providers:
        scanned = scan_by_start.get(int(row["rva"], 0))
        if scanned is not None:
            row["size"] = f"0x{scanned['size'] * 4:x}"
    partition_vtables = list(scan_vtables)
    for row in vtable_rows:
        rva = int(row["vtable_rva"], 0)
        if rva not in scan_by_start:
            methods = row["method_rvas"].split(";")
            partition_vtables.append({
                "start": rva, "size": int(row["methods"]), "sec": ".rdata",
                "rtti": None, "decorated": None, "base_off": None,
                "code_refs": 0, "head_of_run": True,
                "first": int(methods[0], 0), "conf": "runtime-class",
            })
    partition_vtables.sort(key=lambda row: row["start"])

    starts = {int(row["rva"], 0): "" for row in disasm}
    starts.update({rva: starts.get(rva, "") for rva in fpo})
    for rva in eh_partition:
        starts[rva] = "eh"
    for rva in helpers:
        if rva < eh_tail:
            starts[rva] = "helper"
    for row in thunk_rows:
        rva = int(row["rva"], 0)
        if starts.get(rva) != "helper":
            starts[rva] = "thunk"

    exact: dict[int, tuple[int, str, str]] = {}
    for rva, size in fpo.items():
        _add_extent(exact, rva, size, "FPO",
                    "IMAGE_DEBUG_TYPE_FPO exact function extent")
    for rva, (size, evidence) in helpers.items():
        _add_extent(exact, rva, size, ".CRT$XC", evidence)
    for row in thunk_rows:
        _add_extent(exact, int(row["rva"], 0), int(row["size"], 0), "IAT thunk",
                    row["evidence"])

    function_rows = [{"rva": _hex(rva), "kind": kind}
                     for rva, kind in sorted(starts.items())]
    manual_rows = function_rows
    if FUNCTIONS.is_file():
        try:
            _manual_banner, manual_fields, loaded = read_tsv(FUNCTIONS)
            if manual_fields == ["rva", "kind"]:
                manual_rows = loaded
        except ValueError:
            pass
    exact_rows = [{"rva": _hex(rva), "size": f"0x{size:x}", "source": source,
                   "evidence": evidence}
                  for rva, (size, source, evidence) in sorted(exact.items())]
    data_rows, data_extent_rows = _build_data(
        pe, groups, dyninit_rows, xi, xc, runtime_records, partition_vtables,
        reloc_sites)
    ordered_starts = sorted({int(row["rva"], 0) for row in manual_rows})
    e9_runs = []
    current = []
    for rva in ordered_starts:
        if pe.read(rva, 1) == b"\xe9" and current and rva == current[-1] + 5:
            current.append(rva)
        else:
            if current:
                e9_runs.append(current)
            current = [rva] if pe.read(rva, 1) == b"\xe9" else []
    if current:
        e9_runs.append(current)
    max_e9_run = max(map(len, e9_runs), default=0)
    text_section = pe.section(".text")
    helper_bytes = sum(size for size, _evidence in helpers.values())
    summary_rows = [
        {"category": "manual function census", "count": str(len(manual_rows)),
         "bytes": "", "evidence": "initial analyzer/FPO/structure seed; manual thereafter"},
        {"category": "analyzer start evidence", "count": str(len(disasm)), "bytes": "",
         "evidence": "pinned radare2 -AA/aflj; starts only"},
        {"category": "exact FPO records", "count": str(len(fpo)),
         "bytes": str(sum(fpo.values())), "evidence": "IMAGE_DEBUG_TYPE_FPO"},
        {"category": "EH unwind partition", "count": str(len(eh_partition)),
         "bytes": str(text_hi - eh_tail), "evidence": "global FuncInfo action closure"},
        {"category": "C++ initializer helpers", "count": str(len(helpers)),
         "bytes": str(helper_bytes), "evidence": ".CRT$XC entry/forwarder closure"},
        {"category": "IAT jump thunks", "count": str(len(thunk_rows)),
         "bytes": str(sum(int(row["size"], 0) for row in thunk_rows)),
         "evidence": "exact FPO bodies or contiguous six-byte ff25 <IAT> bands"},
        {"category": "incremental-link ILT", "count": "0", "bytes": "0",
         "evidence": f"no dense five-byte E9 island; maximum contiguous run={max_e9_run}"},
        {"category": "virtual .text linker pad", "count": "0", "bytes": "0",
         "evidence": "final EH registration stub ends at PE virtual .text edge"},
        {"category": "raw-only file alignment", "count": "1",
         "bytes": str(text_section["rsize"] - text_section["vsize"]),
         "evidence": "outside virtual .text; not loaded code and not a function"},
        {"category": "MFC runtime classes", "count": str(len(runtime_rows)),
         "bytes": str(len(runtime_rows) * 24), "evidence": "six-dword CRuntimeClass records"},
        {"category": "GetRuntimeClass vtables", "count": str(len(vtable_rows)),
         "bytes": str(sum(int(row["size"], 0) for row in vtable_rows)),
         "evidence": "slot-0 CRuntimeClass return witness"},
        {"category": "executable vtable census", "count": str(len(partition_vtables)),
         "bytes": str(sum(row["size"] * 4 for row in partition_vtables)),
         "evidence": "RTTI/code vptr refs plus GetRuntimeClass proof"},
    ]
    link_rows = [
        {"lo_rva": _hex(text_lo), "hi_rva": _hex(eh_tail), "name": "text-body",
         "space": "text", "class": "mixed",
         "evidence": "PE .text start to first out-of-line /GX action"},
        {"lo_rva": _hex(eh_tail), "hi_rva": _hex(text_hi), "name": "eh-funclets",
         "space": "text", "class": "compiler",
         "evidence": "FuncInfo action closure; final registration stub ends at edge"},
    ]
    for section in pe.sections:
        if section["name"] == ".rdata":
            link_rows.append({"lo_rva": _hex(section["va"]),
                              "hi_rva": _hex(section["va"] + section["vsize"]),
                              "name": "rdata", "space": "rdata", "class": "mixed",
                              "evidence": "PE .rdata virtual extent"})
        elif section["name"] == ".data":
            raw_end = section["va"] + section["rsize"]
            link_rows.extend((
                {"lo_rva": _hex(section["va"]), "hi_rva": _hex(raw_end),
                 "name": "data-init", "space": "data", "class": "mixed",
                 "evidence": "PE .data raw extent"},
                {"lo_rva": _hex(raw_end),
                 "hi_rva": _hex(section["va"] + section["vsize"]),
                 "name": "bss", "space": "bss", "class": "mixed",
                 "evidence": "PE .data loader-zero tail"},
            ))
        elif section["name"] == ".idata":
            link_rows.append({"lo_rva": _hex(section["va"]),
                              "hi_rva": _hex(section["va"] + max(section["vsize"],
                                                                   section["rsize"])),
                              "name": "idata", "space": "idata", "class": "library",
                              "evidence": "PE .idata mapped extent"})
    required_starts = {rva: "" for rva in fpo}
    required_starts.update({rva: "eh" for rva in eh_partition})
    required_starts.update({rva: "helper" for rva in helpers if rva < eh_tail})
    required_starts.update({int(row["rva"], 0): "thunk" for row in thunk_rows
                            if int(row["rva"], 0) not in helpers})
    return {
        "sha": sha, "disasm": disasm, "functions": function_rows,
        "function_extents": exact_rows, "eh_groups": group_rows,
        "eh_actions": action_rows, "dyninit": dyninit_rows, "thunks": thunk_rows,
        "runtime_classes": runtime_rows, "vtables": vtable_rows,
        "data_vtables": vtable_providers, "data": data_rows,
        "scan_vtables": partition_vtables,
        "data_extents": data_extent_rows, "link_bands": link_rows,
        "frame_handler": frame_handler, "eh_tail": eh_tail, "xi": xi, "xc": xc,
        "initterm": initterm,
        "required_starts": required_starts,
        "manual_function_count": len(manual_rows),
        "partition_summary": summary_rows,
    }


def _write_table(path: Path, sha: str, banner: list[str], fields: list[str], rows,
                 write: bool) -> bool:
    complete_banner = [f"# retail_sha256={sha}", *banner]
    if write:
        changed = write_tsv(path, complete_banner, fields, rows)
        print(f"[retail-partition] {'wrote' if changed else 'exact'} "
              f"{path.relative_to(REPO)}")
        return True
    old_banner, old_fields, old_rows = read_tsv(path)
    expected_banner = complete_banner
    exact = old_banner == expected_banner and old_fields == fields and old_rows == rows
    print(f"[retail-partition] {'exact' if exact else 'DRIFT'} {path.relative_to(REPO)}")
    return exact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=retail_exe())
    parser.add_argument("--disasm-source", type=Path,
                        help="radare2 aflj TSV used to seed/update functions_disasm.tsv")
    parser.add_argument("--bootstrap-functions", action="store_true",
                        help="one-time seed of manually maintained functions.tsv")
    parser.add_argument("--bootstrap-data", action="store_true",
                        help="one-time seed of manually maintained data.tsv")
    parser.add_argument("--bootstrap-vtables", action="store_true",
                        help="one-time seed of manually maintained data_vtables.tsv")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    pe = Pe(args.exe)
    source = args.disasm_source or DISASM
    if not source.is_file():
        parser.error("no analyzer-start census; pass --disasm-source for the first write")
    result = generate(pe, source)
    if (args.bootstrap_functions or args.bootstrap_data
            or args.bootstrap_vtables) and not args.write:
        parser.error("--bootstrap-functions/--bootstrap-data/--bootstrap-vtables "
                     "require --write")
    specs = (
        (DISASM, ["# Analyzer starts are evidence only; sizes never override FPO/structural extents."],
         ["rva", "size", "real_size", "instructions", "name", "source"], result["disasm"]),
        (FUNCTION_EXTENTS, ["# Exact executable-native extents; these override derived rooms."],
         ["rva", "size", "source", "evidence"], result["function_extents"]),
        (EH_GROUPS, ["# Every valid VC5 /GX registration stub and its FuncInfo closure."],
         ["stub_rva", "stub_size", "frame_handler_rva", "funcinfo_rva", "max_state",
          "unwind_map_rva", "try_blocks", "try_map_rva", "ip_map_entries", "ip_map_rva",
          "action_refs", "unique_actions", "tail_actions", "owner_ref_sites", "evidence"],
         result["eh_groups"]),
        (EH_ACTIONS, ["# Unique FuncInfo-referenced unwind/catch action addresses."],
         ["action_rva", "region", "roles", "group_stubs", "map_slots", "references"],
         result["eh_actions"]),
        (DYNINIT, ["# _cinit .CRT$XI/.CRT$XC slots and exact entry/target extents."],
         ["table", "slot_rva", "entry_rva", "target_rva", "entry_size", "target_size",
          "role", "evidence"], result["dyninit"]),
        (THUNKS, ["# Pure six-byte bodies in exact FPO records or contiguous retail IAT-stub bands."],
         ["rva", "size", "iat_rva", "import", "evidence"], result["thunks"]),
        (RUNTIME_CLASSES, ["# MFC 4.x CRuntimeClass records recovered structurally from retail."],
         ["class", "rva", "size", "name_rva", "object_size", "own_bytes", "base_class",
          "base_rva", "schema", "dynamic", "create_rva", "next_rva"],
         result["runtime_classes"]),
        (VTABLES, ["# All GetRuntimeClass-proven vtable starts; one class may own several views."],
         ["vtable_rva", "size", "methods", "class", "runtime_class_rva", "getrc_slot",
          "method_rvas", "evidence"], result["vtables"]),
        (DATA_EXTENTS, ["# Exact executable-native data extents; these override derived rooms."],
         ["rva", "size", "source", "evidence"], result["data_extents"]),
        (LINK_BANDS, ["# Coarse executable-native layout with the terminal EH band proven."],
         ["lo_rva", "hi_rva", "name", "space", "class", "evidence"],
         result["link_bands"]),
        (PARTITION_SUMMARY, ["# Auditable zero/nonzero partition facts; raw padding is not code."],
         ["category", "count", "bytes", "evidence"], result["partition_summary"]),
    )
    checks = [_write_table(path, result["sha"], banner, fields, rows, args.write)
              for path, banner, fields, rows in specs]
    function_banner = [f"# retail_sha256={result['sha']}",
        "# Manually maintained after the initial analyzer/FPO/structure bootstrap.",
        "# Generators validate required executable-native starts but never rewrite this file."]
    if args.bootstrap_functions:
        write_tsv(FUNCTIONS, function_banner, ["rva", "kind"], result["functions"])
        print("[retail-partition] bootstrapped config/retail/functions.tsv; "
              "it is manual from this point forward")
    else:
        try:
            _banner, fields, rows = read_tsv(FUNCTIONS)
            actual = {int(row["rva"], 0): row.get("kind", "") for row in rows}
            missing = sorted(rva for rva in result["required_starts"] if rva not in actual)
            wrong = sorted((rva, kind, actual.get(rva, ""))
                           for rva, kind in result["required_starts"].items()
                           if kind and rva in actual and actual[rva] != kind)
            functions_ok = fields == ["rva", "kind"] and not missing and not wrong
        except (OSError, ValueError):
            functions_ok, missing, wrong = False, [], []
        print(f"[retail-partition] {'valid' if functions_ok else 'INVALID'} "
              "config/retail/functions.tsv (manual census; "
              f"missing={len(missing)}, wrong-kind={len(wrong)})")
        checks.append(functions_ok)
    data_banner = [f"# retail_sha256={result['sha']}",
        "# Manually maintained after the initial executable-structure bootstrap.",
        "# Generators validate required executable-native starts but never rewrite this file."]
    if args.bootstrap_data:
        write_tsv(DATA, data_banner, ["rva", "kind"], result["data"])
        print("[retail-partition] bootstrapped config/retail/data.tsv; "
              "it is manual from this point forward")
    else:
        required_data = {int(row["rva"], 0): row["kind"] for row in result["data"]}
        try:
            _banner, fields, rows = read_tsv(DATA)
            actual = {int(row["rva"], 0): row.get("kind", "") for row in rows}
            data_missing = sorted(rva for rva in required_data if rva not in actual)
            data_wrong = sorted((rva, kind, actual.get(rva, ""))
                                for rva, kind in required_data.items()
                                if rva in actual and actual[rva] != kind)
            data_ok = fields == ["rva", "kind"] and not data_missing and not data_wrong
        except (OSError, ValueError):
            data_ok, data_missing, data_wrong = False, [], []
        print(f"[retail-partition] {'valid' if data_ok else 'INVALID'} "
              "config/retail/data.tsv (manual census; "
              f"missing={len(data_missing)}, wrong-kind={len(data_wrong)})")
        checks.append(data_ok)
    vtable_banner = [f"# retail_sha256={result['sha']}",
        "# Manually reviewed after the initial runtime-class bootstrap.",
        "# `rom1 verify vtable-scan --write` refreshes executable/archive proof."]
    if args.bootstrap_vtables:
        write_tsv(DATA_VTABLES, vtable_banner,
                  ["rva", "size", "name", "kind", "note"],
                  result["data_vtables"])
        print("[retail-partition] bootstrapped config/retail/data_vtables.tsv; "
              "it is manual from this point forward")
    else:
        required_vtables = {row["start"]: row["size"] * 4
                            for row in result["scan_vtables"]}
        actual_vtables = {}
        vtable_schema_ok = True
        try:
            _banner, fields, rows = read_tsv(DATA_VTABLES)
            vtable_schema_ok &= fields == ["rva", "size", "name", "kind", "note"]
            actual_vtables.update({int(row["rva"], 0): int(row["size"], 0)
                                   for row in rows})
            _banner, fields, rows = read_tsv(DATA_STATIC_LIBS)
            vtable_schema_ok &= fields == ["rva", "size", "name", "unit", "note"]
            actual_vtables.update({int(row["rva"], 0): int(row["size"], 0)
                                   for row in rows
                                   if row["name"].startswith("??_7")})
            vtable_missing = sorted(rva for rva in required_vtables
                                    if rva not in actual_vtables)
            vtable_wrong = sorted((rva, size, actual_vtables.get(rva))
                                  for rva, size in required_vtables.items()
                                  if rva in actual_vtables
                                  and actual_vtables[rva] != size)
            vtables_ok = vtable_schema_ok and not vtable_missing and not vtable_wrong
        except (OSError, ValueError):
            vtables_ok, vtable_missing, vtable_wrong = False, [], []
        print(f"[retail-partition] {'valid' if vtables_ok else 'INVALID'} "
              "config/retail/data_vtables.tsv + data_static_libs.tsv "
              "(manual providers; "
              f"missing={len(vtable_missing)}, wrong-size={len(vtable_wrong)})")
        checks.append(vtables_ok)
    tail_actions = sum(row["region"] == "tail" for row in result["eh_actions"])
    helper_count = sum(row["kind"] == "helper" for row in result["functions"])
    print(f"[retail-partition] {result['manual_function_count']} manual function starts "
          f"({len(result['functions'])} required by generated evidence); "
          f"{len(result['eh_groups'])} EH groups / {tail_actions} tail actions; "
          f"{helper_count} XC helpers; {len(result['thunks'])} IAT thunks; "
          f"{len(result['runtime_classes'])} runtime classes / "
          f"{len(result['vtables'])} vtable starts")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
