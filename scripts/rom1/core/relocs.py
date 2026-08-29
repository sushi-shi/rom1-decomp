"""The checked executable-derived absolute-relocation site authority."""

from __future__ import annotations

from pathlib import Path

from rom1.core.paths import RETAIL


def load(path: Path | None = None) -> list[int]:
    manifest = path or RETAIL / "relocs.tsv"
    sites: list[int] = []
    for line_no, line in enumerate(manifest.read_text().splitlines(), 1):
        if not line or line.startswith("#") or line == "site_rva\tkind":
            continue
        fields = line.split("\t")
        if len(fields) != 2 or fields[1] != "dir32":
            raise ValueError(f"{manifest}:{line_no}: expected RVA<TAB>dir32")
        sites.append(int(fields[0], 0))
    if sites != sorted(set(sites)):
        raise ValueError(f"{manifest}: relocation RVAs are not unique and sorted")
    return sites
