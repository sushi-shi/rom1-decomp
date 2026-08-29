"""rom1.ghidra - the one-way export: the reconstruction, as a Ghidra project.

    rom1 ghidra build  [--force] [--aggressive] [--no-bookmarks] [--timeout S]
    rom1 ghidra update [--force] [--no-bookmarks] [--timeout S]
                                          re-apply after the Model moved
    rom1 ghidra verify [rva ...] [--timeout S]
                                          read chosen addresses back OUT
    rom1 ghidra status                  what exists, and is it stale
    rom1 ghidra export [--out P] [--quiet]   the payload alone, no Ghidra

Every module is also a direct entry: `python3 -m rom1.ghidra.export`.

ONE-WAY, BY RULING. Ghidra is a viewer for humans who want to browse a labelled
ALLODS.EXE; matching works from `rom1 sema disasm` assembly and never from a
decompile. Nothing produced here flows back - not a boundary, not a type, not a
name. Where Ghidra's auto-carve and the census disagree the census wins, which
is why config/retail/library_labels.csv is tracked at all: Ghidra 12 carves
FEWER functions than the census admits.

The layering:
    export.py    the Model + link bands -> one self-contained payload; the only
                 place that decides what the viewer is told (pure python)
    project.py   build / update / verify / status, and the digest stamp that
                 makes an unchanged update a hash compare
    apply.py     GhidraScript: payload -> functions, names, plates, types,
                 bands (reads the payload, imports nothing from this tree)
    dump.py      GhidraScript: the read-back used by `verify`
    headless.py  the PyGhidra bootstrap, run in a child interpreter by
                 rom1.tool.ghidra (the only layer that spawns processes)
"""

from __future__ import annotations

import sys

SUBCOMMANDS = {
    "build": "rom1.ghidra.project",
    "update": "rom1.ghidra.project",
    "verify": "rom1.ghidra.project",
    "status": "rom1.ghidra.project",
    "export": "rom1.ghidra.export",
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0 if argv else 2
    sub, rest = argv[0], argv[1:]
    if sub not in SUBCOMMANDS:
        print(f"rom1 ghidra: unknown verb {sub!r} (have: "
              f"{', '.join(SUBCOMMANDS)})", file=sys.stderr)
        return 2
    import importlib
    mod = importlib.import_module(SUBCOMMANDS[sub])
    # project.py takes the verb as its first argument; export.py does not
    return mod.main([sub, *rest] if sub != "export" else rest)
