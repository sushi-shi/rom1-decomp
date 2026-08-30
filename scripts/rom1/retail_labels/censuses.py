"""rom1.retail_labels.censuses - the base censuses: structure only.

functions.tsv and data.tsv contribute STARTS and KINDS.  Their maximum room is
derived to the next row, but executable-native exact extents in the companion
``function_extents.tsv`` / ``data_extents.tsv`` tables override that room.
Identity never comes from here - that is the providers' job.
"""

from __future__ import annotations

from pathlib import Path

from rom1.core.paths import RETAIL
from rom1.core.pe import image
from rom1.core.tsv import read as read_tsv

FUNCTION_KINDS = ("", "thunk", "eh", "helper", "pad")
DATA_KINDS = ("", "string", "fppool", "vtable", "rtti", "ehtable", "guard",
              "common", "copy", "pad")



def _rows(path: Path, kinds: tuple[str, ...],
          in_range) -> list[dict]:
    _b, _h, raw = read_tsv(path)
    rows = []
    for r in raw:
        rva = int(r["rva"], 16)
        kind = r.get("kind", "").strip()
        if kind not in kinds:
            raise ValueError(f"{path}: unknown kind {kind!r} at 0x{rva:08x}")
        if not in_range(rva):
            raise ValueError(f"{path}: 0x{rva:08x} outside its address space")
        rows.append({"rva": rva, "kind": kind})
    rows.sort(key=lambda r: r["rva"])
    for a, b in zip(rows, rows[1:]):
        if a["rva"] == b["rva"]:
            raise ValueError(f"{path}: duplicate row 0x{a['rva']:08x}")
    return rows


def _extents(path: Path) -> dict[int, int]:
    _banner, fields, raw = read_tsv(path)
    if "rva" not in fields or "size" not in fields:
        raise ValueError(f"{path}: extent table needs rva and size")
    out = {}
    for row in raw:
        rva, size = int(row["rva"], 0), int(row["size"], 0)
        if size <= 0:
            raise ValueError(f"{path}: non-positive extent at 0x{rva:08x}")
        if rva in out:
            raise ValueError(f"{path}: duplicate extent at 0x{rva:08x}")
        out[rva] = size
    return out


def functions(path: Path | None = None) -> list[dict]:
    """[{rva, kind, size}] with retail exact extents taking precedence."""
    text_lo, text_end = image().text_span()
    rows = _rows(path or RETAIL / "functions.tsv", FUNCTION_KINDS,
                 lambda v: text_lo <= v < text_end)
    exact = _extents(RETAIL / "function_extents.tsv") if path is None else {}
    admitted = {row["rva"] for row in rows}
    orphan = sorted(set(exact) - admitted)
    if orphan:
        raise ValueError(f"function_extents: 0x{orphan[0]:08x} is not an admitted start")
    for row, nxt in zip(rows, rows[1:] + [None]):
        room = (nxt["rva"] if nxt else text_end) - row["rva"]
        size = exact.get(row["rva"], room)
        if size > room:
            raise ValueError(f"function extent at 0x{row['rva']:08x} is 0x{size:x}, "
                             f"crossing next start after 0x{room:x} bytes")
        row["size"] = size
    return rows


def data(path: Path | None = None) -> list[dict]:
    """[{rva, kind, region, size}] - size derived within the row's region;
    the region edges come from the retail PE's section table."""
    regions = image().data_regions()

    def region(v):
        return next((k for k, (lo, hi) in regions.items() if lo <= v < hi),
                    None)
    rows = _rows(path or RETAIL / "data.tsv", DATA_KINDS,
                 lambda v: region(v) is not None)
    exact = _extents(RETAIL / "data_extents.tsv") if path is None else {}
    admitted = {row["rva"] for row in rows}
    orphan = sorted(set(exact) - admitted)
    if orphan:
        raise ValueError(f"data_extents: 0x{orphan[0]:08x} is not an admitted start")
    for r in rows:
        r["region"] = region(r["rva"])
    # data+bss are ONE PE section (.data raw bytes + loader-zero tail), so an
    # extent may legitimately cross the rawsize edge - a datum at the edge is
    # partly stored, partly zero-fill. Regions stay as reporting tags; the
    # extent cap only honours REAL edges (section ends).
    contiguous = {"data": "bss"}
    for row, nxt in zip(rows, rows[1:] + [None]):
        hi = regions[row["region"]][1]
        if nxt is not None and (nxt["region"] == row["region"]
                                or contiguous.get(row["region"]) == nxt["region"]):
            hi = nxt["rva"]
        elif contiguous.get(row["region"]):
            hi = regions[contiguous[row["region"]]][1]
        room = hi - row["rva"]
        size = exact.get(row["rva"], room)
        if size > room:
            raise ValueError(f"data extent at 0x{row['rva']:08x} is 0x{size:x}, "
                             f"crossing next start after 0x{room:x} bytes")
        row["size"] = size
    return rows


def link_order_bands(path: Path | None = None) -> list[tuple[int, int, str]]:
    """[(lo, hi, unit)] from link_order.tsv - per-unit retail contribution
    bands (positional columns; class=comdat-owner rows carry no span)."""
    out = []
    for line in (path or RETAIL / "link_order.tsv").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split("\t")
        if len(f) >= 4 and f[2].startswith("0x"):
            out.append((int(f[2], 16), int(f[3], 16), f[1]))
    out.sort()
    return out


def link_bands(path: Path | None = None) -> list[tuple[int, int, str]]:
    """[(lo, hi, band)] - the coarse link-layout bands, sorted."""
    _b, fields, raw = read_tsv(path or RETAIL / "link_bands.tsv")
    if {"lo_rva", "hi_rva", "name"}.issubset(fields):
        keys = ("lo_rva", "hi_rva", "name")
    elif {"lo", "hi", "band"}.issubset(fields):
        # Retain compatibility with the Gruntz schema imported by this tool.
        keys = ("lo", "hi", "band")
    else:
        raise ValueError(f"link_bands: unsupported fields {fields}")
    lo_key, hi_key, name_key = keys
    out = [(int(r[lo_key], 16), int(r[hi_key], 16), r[name_key]) for r in raw]
    out.sort()
    for (alo, ahi, an), (blo, _bh, bn) in zip(out, out[1:]):
        if ahi > blo:
            raise ValueError(f"link_bands: {an} overlaps {bn} at 0x{blo:08x}")
    return out
