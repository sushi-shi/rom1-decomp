"""Serialization/deserialization candidate wall over the retail image.

This is discovery, not naming.  It joins three independent facts:

* every recovered CObject-derived vtable's slot 2 (CObject::Serialize), with
  the inherited empty body at 0x001950 excluded;
* effective callers, through incremental-link thunks, of the reviewed
  CArchive/CFile/CMemFile roots in config/retail/serde_roots.tsv;
* effective callers of the narrow stdio read/write roots used by file-format
  code (fread/fgets/sscanf and fwrite/fputs).

The generated report is written only under build/gen.  The campaign wall at
config/retail/serde_candidates.tsv is manually maintained after bootstrap and
is checked by ``rom1 verify serde-coverage``; this module never edits it.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from rom1.core.paths import BUILD, RETAIL
from rom1.core.tsv import read as read_tsv, write as write_tsv
from rom1.sema.image import retail
from rom1.sema.index import index, short_name
from rom1.sema.strings import by_function
from rom1.sema.xref import effective_incoming

ROOTS = RETAIL / "serde_roots.tsv"
VTABLES = RETAIL / "vtables.tsv"
RUNTIME_CLASSES = RETAIL / "runtime_classes.tsv"
REPORT = BUILD / "gen/serde_candidates.tsv"
DEFAULT_SERIALIZE = 0x001950
SERIALIZE_SLOT = 2
SKIP_KINDS = {"thunk", "eh", "pad"}


@dataclass
class Candidate:
    rva: int
    size: int
    signals: set[str] = field(default_factory=set)
    roots: set[int] = field(default_factory=set)
    classes: set[str] = field(default_factory=set)
    name: str = ""
    channel: str = ""
    literals: list[str] = field(default_factory=list)

    def signal_text(self) -> str:
        return ",".join(sorted(self.signals))


def _rows(path: Path, schema: list[str]) -> list[dict[str, str]]:
    _banner, fields, rows = read_tsv(path)
    if fields != schema:
        raise ValueError(f"{path}: expected schema {schema}, got {fields}")
    return rows


def root_rows() -> list[dict[str, str]]:
    return _rows(ROOTS, ["signal", "rva", "role", "direction", "evidence"])


def _cobject_classes() -> set[str]:
    """Every runtime class whose recovered base chain reaches CObject."""
    rows = _rows(
        RUNTIME_CLASSES,
        ["class", "rva", "size", "name_rva", "object_size", "own_bytes",
         "base_class", "base_rva", "schema", "dynamic", "create_rva",
         "next_rva"],
    )
    base = {row["class"]: row["base_class"] for row in rows}
    memo: dict[str, bool] = {"CObject": True}

    def derives(name: str, active: set[str] | None = None) -> bool:
        if name in memo:
            return memo[name]
        active = set() if active is None else active
        if name in active:
            memo[name] = False
            return False
        active.add(name)
        parent = base.get(name, "")
        result = bool(parent) and derives(parent, active)
        memo[name] = result
        return result

    return {name for name in base if derives(name)}


def _candidate(out: dict[int, Candidate], rva: int) -> Candidate | None:
    idx = index()
    body = idx.func(rva)
    if body is None or body.kind in SKIP_KINDS:
        return None
    row = out.get(rva)
    if row is None:
        hits = [text for _addr, text in by_function().get(rva, ())]
        row = Candidate(
            rva=rva,
            size=body.size,
            name=short_name(body.name) if body.name else "",
            channel=body.channel or "",
            literals=hits,
        )
        out[rva] = row
    return row


def _virtual_serializers(out: dict[int, Candidate]) -> None:
    classes = _cobject_classes()
    rows = _rows(
        VTABLES,
        ["vtable_rva", "size", "methods", "class", "runtime_class_rva",
         "getrc_slot", "method_rvas", "evidence"],
    )
    for table in rows:
        if table["class"] not in classes:
            continue
        methods = [int(value, 0) for value in table["method_rvas"].split(";")
                   if value]
        if len(methods) <= SERIALIZE_SLOT:
            continue
        rva = methods[SERIALIZE_SLOT]
        if rva == DEFAULT_SERIALIZE:
            continue
        row = _candidate(out, rva)
        if row is not None:
            row.signals.add("archive-vslot2")
            row.classes.add(table["class"])


def _primitive_callers(out: dict[int, Candidate]) -> None:
    roots = root_rows()
    root_rvas = {int(row["rva"], 0) for row in roots}
    for root in roots:
        rva = int(root["rva"], 0)
        for owner, opcode, _site, _via in effective_incoming(rva):
            if opcode is None or owner is None or owner.rva in root_rvas:
                continue
            row = _candidate(out, owner.rva)
            if row is not None:
                row.signals.add(root["signal"])
                row.roots.add(rva)


def discover() -> dict[int, Candidate]:
    out: dict[int, Candidate] = {}
    _virtual_serializers(out)
    _primitive_callers(out)
    return dict(sorted(out.items()))


def generated_rows(candidates: dict[int, Candidate]) -> list[dict[str, str]]:
    return [
        {
            "rva": f"0x{row.rva:06x}",
            "size": f"0x{row.size:x}",
            "signals": row.signal_text(),
            "classes": ",".join(sorted(row.classes)),
            "roots": ",".join(f"0x{rva:06x}" for rva in sorted(row.roots)),
            "name": row.name,
            "channel": row.channel,
            "literals": " | ".join(row.literals[:8]),
        }
        for row in candidates.values()
    ]


def write_report(candidates: dict[int, Candidate]) -> bool:
    return write_tsv(
        REPORT,
        ["# Generated by rom1 sema serde / rom1 verify serde-coverage.",
         "# Scratch discovery output; never an authority or source-claim file."],
        ["rva", "size", "signals", "classes", "roots", "name", "channel",
         "literals"],
        generated_rows(candidates),
    )


def summary(candidates: dict[int, Candidate]) -> list[str]:
    signals = sorted({signal for row in candidates.values()
                      for signal in row.signals})
    out = [f"{len(candidates)} distinct serialization/deserialization candidates"]
    for signal in signals:
        out.append(f"  {signal:<20} "
                   f"{sum(signal in row.signals for row in candidates.values()):4d}")
    claimed = sum(bool(row.channel) for row in candidates.values())
    named = sum(bool(row.name) for row in candidates.values())
    out.append(f"  named {named}; claimed {claimed}; unclaimed "
               f"{len(candidates) - claimed}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 sema serde", description=__doc__)
    ap.add_argument("--write-report", action="store_true",
                    help="write the derived scratch table under build/gen")
    ap.add_argument("--rva", help="show one candidate RVA")
    ap.add_argument("--all", action="store_true", help="list every candidate")
    args = ap.parse_args(argv)
    candidates = discover()
    if args.write_report:
        write_report(candidates)
        print(f"wrote {REPORT.relative_to(BUILD.parent)}")
    print("\n".join(summary(candidates)))
    rows = candidates.values()
    if args.rva:
        wanted = int(args.rva, 0)
        rows = [candidates[wanted]] if wanted in candidates else []
    elif not args.all:
        return 0
    for row in rows:
        cls = f" classes={','.join(sorted(row.classes))}" if row.classes else ""
        name = f" {row.name}" if row.name else ""
        print(f"0x{row.rva:06x} 0x{row.size:<5x} {row.signal_text()}{cls}{name}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
