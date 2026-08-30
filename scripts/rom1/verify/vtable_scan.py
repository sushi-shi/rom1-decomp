"""rom1.verify.vtable_scan - every vtable in ALLODS.EXE, with exact sizes.

Three independent retail signals (ported; rebuilt on rom1.sema.image):
  1. a maximal stride-4 run of DATA-section recovered-DIR32 sites whose values
     all point into .text is a band of one-or-more adjacent vtables;
  2. /GR RTTI: `vtable-4` holds a Complete Object Locator pointer - CONFIRMS
     a start, names it, and carries the MI base offset;
  3. a CODE DIR32 onto a run member is a ctor/dtor vptr stamp - a real start
     even without RTTI. `call/jmp ds:[slot]` (FF15/FF25 devirtualised calls)
     are excluded - they point mid-vtable and fabricate phantom starts.

Cutting each run at {COL starts} u {code-referenced starts} de-merges
adjacent vtables and yields exact per-vtable entry counts. Confidence:
`rtti` / `code-ref` (>=2 slots, .rdata) / `code-ref-weak` / `unref` (run
head with no signal: EH/jump tables, NOT a vtable).

    python3 -m rom1.verify.vtable_scan [--new] [--holds 0xRVA] [--dump 0xRVA]
    python3 -m rom1.verify.vtable_scan --write
"""

from __future__ import annotations

import re
from functools import lru_cache


def demangle(s: str) -> str:
    for pre in (".?AV", ".?AU", ".?AW", ".?AT"):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    if s.endswith("@@"):
        s = s[:-2]
    parts = [x for x in s.split("@") if x]
    return "::".join(reversed(parts)) if parts else s


def vftable_name(decorated: str) -> str:
    """'.?AVCFoo@@' -> '??_7CFoo@@6B@' (base_off==0 primary tables only)."""
    s = decorated
    for pre in (".?AV", ".?AU", ".?AW", ".?AT"):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    return "??_7" + s + "6B@"


@lru_cache(maxsize=1)
def scan() -> list[dict]:
    """The discovered vtable list (each: start, size, sec, rtti, decorated,
    base_off, code_refs, head_of_run, first, conf)."""
    from rom1.sema.image import retail
    img = retail()
    base = img.base

    # --- RTTI: TypeDescriptors + COLs ---------------------------------------
    td: dict[int, str] = {}          # td VA -> decorated name
    data = img.pe.data
    for m in re.finditer(rb"\.\?A[VUWT][\w@?$]+@@\x00", data):
        so = m.start()
        rva = None
        for s in img.pe.sections:
            if s["rptr"] <= so < s["rptr"] + s["rsize"]:
                rva = so - s["rptr"] + s["va"]
                break
        if rva is None:
            continue
        td[(rva - 8) + base] = m.group(0)[:-1].decode("latin1")
    col: dict[int, tuple[str, int]] = {}
    rd = img.pe.section(".rdata")
    for a in range(rd["va"], rd["va"] + rd["rsize"] - 20, 4):
        if img.u32(a) != 0:
            continue
        ptd = img.u32(a + 12)
        if ptd in td:
            col[a + base] = (td[ptd], img.u32(a + 4))

    # --- data-section code-pointer runs -------------------------------------
    reloc = img.reloc
    relset = set(reloc)
    sites = sorted(s for s in reloc if not img.is_text(s))
    runs: list[tuple[int, int]] = []
    i, n = 0, len(sites)
    while i < n:
        s0 = sites[i]
        if not img.is_text(reloc[s0]):
            i += 1
            continue
        last, j = s0, i + 1
        while j < n and sites[j] == last + 4 and img.is_text(reloc[sites[j]]):
            last = sites[j]
            j += 1
        runs.append((s0, last + 4))
        i = j if j > i else i + 1
    members: set[int] = set()
    for lo, hi in runs:
        members.update(range(lo, hi, 4))

    # --- code-referenced starts (vptr stamps) -------------------------------
    code_ref: dict[int, int] = {}
    for s, t in reloc.items():
        if not img.is_text(s) or t not in members:
            continue
        b = img.read(s - 2, 2)
        if b and b[0] == 0xFF and b[1] in (0x15, 0x25):
            continue                      # devirtualised call through a slot
        code_ref[t] = code_ref.get(t, 0) + 1

    col_start: dict[int, tuple[str, int]] = {}
    for lo, hi in runs:
        pv = img.u32(lo - 4) if (lo - 4) in relset else None
        if pv in col:
            col_start[lo] = col[pv]
    for a in members:
        if (a - 4) in relset:
            pv = img.u32(a - 4)
            if pv in col:
                col_start.setdefault(a, col[pv])

    known = set(col_start) | set(code_ref)
    out: list[dict] = []
    for lo, hi in runs:
        cuts = sorted(a for a in known if lo <= a < hi)
        if not cuts or cuts[0] != lo:
            cuts = [lo] + cuts
        cuts = sorted(set(cuts))
        for k, st in enumerate(cuts):
            en = cuts[k + 1] if k + 1 < len(cuts) else hi
            c = col_start.get(st)
            v = dict(start=st, size=(en - st) // 4,
                     sec=img.section_name(st),
                     rtti=demangle(c[0]) if c else None,
                     decorated=c[0] if c else None,
                     base_off=c[1] if c else None,
                     code_refs=code_ref.get(st, 0),
                     head_of_run=(st == lo),
                     first=img.u32(st) - base)
            v["conf"] = confidence(v)
            out.append(v)
    return out


def confidence(v: dict) -> str:
    if v["rtti"]:
        return "rtti"
    if v["code_refs"] and v["size"] >= 2 and v["sec"] == ".rdata":
        return "code-ref"
    if v["code_refs"]:
        return "code-ref-weak"
    return "unref"


REAL_CONF = {"rtti", "code-ref", "code-ref-weak"}


def real_vtables() -> list[dict]:
    return [v for v in scan() if v["conf"] in REAL_CONF]


def proven_vtables() -> list[dict]:
    """Scanner tables plus GetRuntimeClass-proven starts whose first site is
    absent from the recovered relocation stream."""
    from rom1.core.paths import RETAIL
    out = {v["start"]: v for v in real_vtables()}
    _banner, fields, rows = _read_rows(RETAIL / "vtables.tsv")
    if fields and fields != ["vtable_rva", "size", "methods", "class",
                             "runtime_class_rva", "getrc_slot", "method_rvas",
                             "evidence"]:
        raise ValueError("config/retail/vtables.tsv: unexpected schema")
    for row in rows:
        rva = int(row["vtable_rva"], 0)
        if rva in out:
            continue
        methods = row["method_rvas"].split(";")
        out[rva] = {
            "start": rva, "size": int(row["methods"]), "sec": ".rdata",
            "rtti": None, "decorated": None, "base_off": None,
            "code_refs": 0, "head_of_run": True,
            "first": int(methods[0], 0), "conf": "runtime-class",
        }
    return [out[rva] for rva in sorted(out)]


def vtable_at(start: int) -> dict | None:
    from rom1.sema.image import retail
    if start >= retail().base:
        start -= retail().base
    return next((v for v in proven_vtables() if v["start"] == start), None)


def iter_slots(v: dict):
    """(slot_index, slot_rva, raw_target_rva, body_rva) - ILT thunks chased."""
    from rom1.sema.image import retail
    img = retail()
    for k in range(v["size"]):
        sr = v["start"] + k * 4
        w = img.u32(sr)
        if w is None:
            continue
        raw = w - img.base
        body = img.jmp_target(raw) if img.is_text(raw) else None
        yield k, sr, raw, (raw if body is None else body)


def _fn_label(rva: int) -> str:
    from rom1.model import resolve
    import bisect
    m = resolve()
    starts = [b.rva for b in m.functions]
    i = bisect.bisect_right(starts, rva) - 1
    if i >= 0:
        b = m.functions[i]
        if b.rva <= rva < b.rva + b.size:
            nm = b.name or f"sub_{b.rva:06x}"
            return nm if rva == b.rva else f"{nm}+0x{rva - b.rva:x}"
    return f"sub_{rva:06x}"


def _read_rows(path):
    from rom1.core.tsv import read as read_tsv
    try:
        banner, fields, rows = read_tsv(path)
    except (OSError, ValueError):
        return [], [], []
    return banner, fields, rows


def write_catalog() -> tuple[int, int, int]:
    """Write the reviewed vtable/static-library catalog and census starts.

    RTTI proves a primary vtable's exact MSVC symbol spelling.  It is called
    static-library data only when the pinned SP2 archives contain one unique
    definition of that symbol with exactly the retail table extent.  Every
    other discovered table is deliberately `unresolved`: the executable
    proves its shape, but source ownership/virtuality has not been earned.
    """
    from rom1.core.paths import RETAIL
    from rom1.core.tsv import write as write_tsv
    from rom1.verify import library_data_refs as ldr

    vtable_path = RETAIL / "data_vtables.tsv"
    static_path = RETAIL / "data_static_libs.tsv"
    data_path = RETAIL / "data.tsv"
    vb, vf, old_vtables = _read_rows(vtable_path)
    sb, sf, old_static = _read_rows(static_path)
    db, df, old_data = _read_rows(data_path)
    if vf and vf != ["rva", "size", "name", "kind", "note"]:
        raise ValueError(f"{vtable_path}: unexpected schema {vf}")
    if sf and sf != ["rva", "size", "name", "unit", "note"]:
        raise ValueError(f"{static_path}: unexpected schema {sf}")
    if df != ["rva", "kind"]:
        raise ValueError(f"{data_path}: unexpected schema {df}")

    real = proven_vtables()
    starts = {v["start"] for v in real}
    old_vt_by_rva = {int(r["rva"], 0): r for r in old_vtables}
    old_static_by_rva = {int(r["rva"], 0): r for r in old_static}

    def candidate_names(v):
        old = old_vt_by_rva.get(v["start"]) or old_static_by_rva.get(v["start"])
        names = []
        if old and old.get("name", "").startswith("??_7"):
            names.append(old["name"])
        if v["decorated"] and not v["base_off"]:
            names.append(vftable_name(v["decorated"]))
        return list(dict.fromkeys(names))

    candidates_by_rva = {v["start"]: candidate_names(v) for v in real}
    name_rvas = {}
    for rva, names in candidates_by_rva.items():
        for name in names:
            name_rvas.setdefault(name, set()).add(rva)
    ambiguous_names = {name for name, rvas in name_rvas.items() if len(rvas) > 1}

    _members, by_symbol = ldr._indexes(set(ldr.LIB_FILES))
    game_rows, static_rows = [], []
    for v in real:
        rva, size = v["start"], v["size"] * 4
        old = old_vt_by_rva.get(rva) or old_static_by_rva.get(rva)
        candidates = candidates_by_rva[rva]

        definitions = []
        for name in candidates:
            if name in ambiguous_names:
                continue
            for library in sorted(ldr.LIB_FILES):
                for definition in by_symbol.get((library, name), ()):
                    if definition.size == size and definition.storage in ("data", "rdata"):
                        definitions.append((name, library, definition))
        unique = {(name, library, d.member.name): (name, library, d)
                  for name, library, d in definitions}
        if len(unique) == 1:
            name, library, definition = next(iter(unique.values()))
            static_rows.append({
                "rva": f"0x{rva:06x}", "size": f"0x{size:x}",
                "name": name, "unit": "library_data",
                "note": (f"VC5 SP2 {ldr.LIB_FILES[library]} "
                         f"{definition.member.name}: unique exact symbol+extent"),
            })
            continue

        unique_names = [name for name in candidates if name not in ambiguous_names]
        if old and old.get("name") and old["name"] in unique_names:
            name = old["name"]
        elif unique_names:
            name = unique_names[0]
        else:
            name = f"__rom1_vtable_{rva:06x}"
        facts = [v["conf"], f"{v['size']} exact slots",
                 f"{v['code_refs']} code ref(s)"]
        if v["rtti"]:
            facts.append(f"RTTI {v['rtti']}")
        if v["base_off"]:
            facts.append(f"secondary base+0x{v['base_off']:x}")
        if any(name in ambiguous_names for name in candidates):
            facts.append("retail-duplicate class spelling withheld")
        game_rows.append({
            "rva": f"0x{rva:06x}", "size": f"0x{size:x}",
            "name": name, "kind": "unresolved",
            "note": "; ".join(facts) + "; promote only with reconstructed source",
        })

    # Non-scan rows are hand-owned evidence and survive a catalog refresh.
    game_rows.extend(r for r in old_vtables if int(r["rva"], 0) not in starts)
    static_rows.extend(r for r in old_static if int(r["rva"], 0) not in starts)
    game_rows.sort(key=lambda r: int(r["rva"], 0))
    static_rows.sort(key=lambda r: int(r["rva"], 0))

    data = {int(r["rva"], 0): dict(r) for r in old_data}
    for rva in starts:
        row = data.get(rva)
        if row is not None and row.get("kind") not in ("", "vtable"):
            raise ValueError(f"{data_path}: 0x{rva:06x} is {row['kind']}, not vtable")
        data[rva] = {"rva": f"0x{rva:06x}", "kind": "vtable"}
    data_rows = [data[rva] for rva in sorted(data)]

    retail_sha = next((line for line in vb if line.startswith("# retail_sha256=")),
                      "# retail_sha256=unknown")
    write_tsv(vtable_path,
              [retail_sha,
               "# Hand-owned vtable catalog refreshed only by explicit --write.",
               "# kind=unresolved proves retail structure, not reconstructed source."],
              ["rva", "size", "name", "kind", "note"], game_rows)
    write_tsv(static_path,
              ["# Statically-linked library DATA labels proven against pinned VC5 SP2.",
               "# library_data is the deliberate non-reconstructed holding unit."],
              ["rva", "size", "name", "unit", "note"], static_rows)
    write_tsv(data_path, db, ["rva", "kind"], data_rows)
    return len(real), len(game_rows), len(static_rows)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rom1 verify vtable-scan",
                                 description=__doc__)
    ap.add_argument("--new", action="store_true",
                    help="only starts with no admitted vtable/static-libs row")
    ap.add_argument("--holds", help="which vtable slot(s) resolve to this fn")
    ap.add_argument("--dump", help="the slots of the vtable at this start")
    ap.add_argument("--write", action="store_true",
                    help="refresh manual catalogs from executable/archive proof")
    a = ap.parse_args(argv)

    if a.write:
        if a.new or a.holds or a.dump:
            ap.error("--write cannot be combined with query flags")
        total, game, static = write_catalog()
        print(f"vtable catalog: {total} exact retail tables; {game} unresolved/game, "
              f"{static} unique VC5 SP2 static-library providers")
        return 0

    if a.holds:
        fn = int(a.holds, 16)
        hits = [(v, k, raw != fn) for v in scan()
                if v["sec"] in (".rdata", ".data")
                for k, _sr, raw, body in iter_slots(v) if body == fn]
        print(f"# vtable slots holding 0x{fn:06x} {_fn_label(fn)}")
        if not hits:
            print("  (none)")
            return 1
        for v, k, via in hits:
            cls = v["rtti"] or f"non-rtti {_fn_label(v['first'])}"
            print(f"  vtable 0x{v['start']:06x}  {v['conf']:<9} slot[{k}] "
                  f"(+0x{k * 4:x}){'  via thunk' if via else ''}   {cls}")
        return 0

    if a.dump:
        vt = vtable_at(int(a.dump, 16))
        if vt is None:
            print("# no discovered vtable starts there")
            return 1
        cls = vt["rtti"] or f"non-rtti (first: {_fn_label(vt['first'])})"
        print(f"# vtable 0x{vt['start']:06x}  {vt['conf']}  size={vt['size']}"
              f"  code-refs={vt['code_refs']}  {cls}")
        for k, _sr, raw, body in iter_slots(vt):
            via = f"  (via thunk 0x{raw:x})" if body != raw else ""
            print(f"  slot[{k:2}] (+0x{k * 4:02x}): 0x{body:06x} "
                  f"{_fn_label(body)}{via}")
        return 0

    vts = scan()
    real = proven_vtables()
    from rom1.model import resolve
    admitted = {b.rva for b in resolve().data if b.kind == "vtable"}
    show = [v for v in real if v["start"] not in admitted] if a.new else real
    n_rtti = sum(1 for v in real if v["conf"] == "rtti")
    print(f"# VTABLES: {len(real)} real ({n_rtti} rtti), "
          f"{len(vts) - len(real)} unref run-heads excluded; "
          f"{len(real) - len([v for v in real if v['start'] not in admitted])}"
          f" admitted, {len([v for v in real if v['start'] not in admitted])}"
          f" NOT admitted")
    for v in sorted(show, key=lambda v: v["start"]):
        cls = v["rtti"] or _fn_label(v["first"])
        bo = f" [base+{v['base_off']}]" if v["base_off"] else ""
        mark = "NEW" if v["start"] not in admitted else "ok "
        print(f"  0x{v['start']:06x} {v['sec']:<6} {v['size']:>3} "
              f"{v['conf']:<13} {mark} {cls}{bo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
