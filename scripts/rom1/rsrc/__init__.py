"""rom1.rsrc - the resource section, proven from source.

    rom1 rsrc check               compile src/Allods/Allods.rc with the era
                                    RC.EXE and byte-compare every payload
                                    (type, name, lang, bytes, payload order)
                                    against the retail PE's .rsrc - total
                                    coverage both directions. Exit 0 identical,
                                    1 a real deviation, 2 could not run (no era
                                    rc.exe / unwritable --out / unreadable PE)

src/Allods/Allods.rc plus src/Allods/res/*.{ico,cur} is the ONE carrier of
retail's 75 resources. The era RC.EXE (toolchain r3+, via rom1.tool.rc)
compiles it; the check gate proves it against the retail image itself
(rom1.core.pe). No extracted resource bytes are stored anywhere - the
retail image is the only oracle.
"""

from __future__ import annotations

_SUBS = ("check",)


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if not argv or argv[0] not in _SUBS:
        print(__doc__.strip(), file=sys.stderr)
        what = f"unknown subcommand {argv[0]!r}" if argv else "no subcommand"
        print(f"\nrom1 rsrc: {what} - pick one of: {', '.join(_SUBS)}",
              file=sys.stderr)
        return 2
    sub, rest = argv[0], argv[1:]
    from rom1.rsrc.check import main as check_main
    sys.argv = [f"rom1 rsrc {sub}", *rest]
    return check_main(rest)
