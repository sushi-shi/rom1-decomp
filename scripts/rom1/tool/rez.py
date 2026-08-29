"""rom1.tool.rez - the Monolith RezMgr v1 archive (Rom1.REZ), read-only.

Layer note: every other module here DRIVES a program; this one reads an
artifact. It sits with them because it is era-format knowledge that belongs
next to the other readers of shipped bytes, and because it spawns nothing.

FORMAT (recovered by hand against the shipped archive, 2026-08-20):

  0x00  ASCII banner, `\\r\\nRezMgr Version 1 Copyright (C) 1995 MONOLITH INC.`
        padded with spaces, terminated by 0x1a at 0x7E.
  0x7F  version(4)  rootDirPos(4)  rootDirSize(4)  ... - the FIRST dword after
        the 0x1a, NOT a 4-byte-aligned offset. Reading the header at 0x7C
        yields a plausible-looking but bogus root and the walk finds nothing.

  A directory blob is a flat sequence of entries, each tagged by a leading
  dword:

    type == 1 (directory)  pos(4) size(4) time(4) name(asciiz)
    type == 0 (resource)   pos(4) size(4) time(4) id(4) ext(4, e.g. "DIP\\0")
                           numKeys(4) name(asciiz) key(asciiz) x numKeys
                           ONE TRAILING PAD BYTE

  The pad byte is the whole trap: it exists on RESOURCE entries and NOT on
  directory entries. A parser that omits it desyncs one byte into the second
  entry of every directory, then reads the next type dword straddling the
  boundary and stops - which looks exactly like "this imageset has 2 frames"
  instead of 24, and that is a wrong answer, not a crash.

WHY THIS MATTERS TO THE MATCH: CDDrawWorker::BuildFramesFromArchive (0x1521f0,
byte-exact) derives each frame index by `atoi`-ing the FIRST DIGIT RUN of the
resource name, and InsertFrame keeps a running min/max over those indices.
So `list --index` prints exactly the m_minIndex/m_maxIndex a namespace worker
will end up with, which is what decides whether CSBI_ImageSet::Render draws a
given frame or silently stores m_frame = NULL.

    rom1 tool rez list <archive> [--path SUB] [--index]
    rom1 tool rez extract <archive> <path> <out>
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

HEADER = 0x7F


def _zstr(buf: bytes, off: int) -> tuple[str, int]:
    end = buf.index(b"\0", off)
    return buf[off:end].decode("latin-1"), end + 1


def walk(fh) -> dict[str, list[tuple[str, str, int, int]]]:
    """{directory path: [(name, ext, size, pos)]} for the whole archive."""
    fh.seek(HEADER)
    _ver, rootpos, rootsize = struct.unpack("<3I", fh.read(12))
    out: dict[str, list[tuple[str, str, int, int]]] = {}

    def rec(pos: int, size: int, prefix: list[str]) -> None:
        fh.seek(pos)
        buf = fh.read(size)
        off = 0
        while off + 4 <= len(buf):
            (kind,) = struct.unpack_from("<I", buf, off)
            off += 4
            if kind == 1:
                dpos, dsize, _t = struct.unpack_from("<3I", buf, off)
                off += 12
                name, off = _zstr(buf, off)
                rec(dpos, dsize, prefix + [name])
            elif kind == 0:
                rpos, rsize, _t, _id, ext, nkeys = \
                    struct.unpack_from("<6I", buf, off)
                off += 24
                name, off = _zstr(buf, off)
                for _ in range(nkeys):
                    _key, off = _zstr(buf, off)
                off += 1                      # the resource-only pad byte
                out.setdefault("/".join(prefix), []).append(
                    (name, struct.pack("<I", ext).rstrip(b"\0").decode("latin-1"),
                     rsize, rpos))
            else:
                return                        # not an entry tag: blob ends
    rec(rootpos, rootsize, [])
    return out


def frame_index(name: str) -> int:
    """The index BuildFramesFromArchive derives: atoi of the first digit run."""
    m = re.search(r"\d+", name)
    return int(m.group(0)) if m else 0


def do_list(args) -> int:
    with open(args.archive, "rb") as fh:
        tree = walk(fh)
    want = (args.path or "").upper()
    shown = 0
    for path in sorted(tree):
        if want and want not in path.upper():
            continue
        shown += 1
        print(path)
        idx = []
        for name, ext, size, _pos in sorted(tree[path]):
            n = frame_index(name)
            idx.append(n)
            print(f"    {name}.{ext}  size={size}"
                  + (f"  atoi->{n} (0x{n:x})" if args.index else ""))
        if args.index and idx:
            print(f"    => m_minIndex {min(idx)} (0x{min(idx):x})  "
                  f"m_maxIndex {max(idx)} (0x{max(idx):x})  n={len(idx)}"
                  + (f"  GAPS {sorted(set(range(min(idx), max(idx) + 1)) - set(idx))}"
                     if len(set(idx)) > 1 else ""))
    if not shown:
        print(f"[rez] no directory matches {args.path!r}", file=sys.stderr)
        return 1
    return 0


def do_extract(args) -> int:
    with open(args.archive, "rb") as fh:
        tree = walk(fh)
        want = args.path.upper()
        for path in sorted(tree):
            for name, ext, size, pos in tree[path]:
                full = f"{path}/{name}.{ext}"
                if full.upper() == want:
                    fh.seek(pos)
                    Path(args.out).write_bytes(fh.read(size))
                    print(f"[rez] {full} -> {args.out} ({size} B)")
                    return 0
    print(f"[rez] no resource named {args.path!r} "
          f"(`rom1 tool rez list` shows the tree)", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rom1 tool rez",
                                 description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="verb", required=True)
    ls = sub.add_parser("list", help="list directories and their resources")
    ls.add_argument("archive")
    ls.add_argument("--path", help="only directories whose path contains this")
    ls.add_argument("--index", action="store_true",
                    help="also print the atoi frame index and the min/max a "
                         "namespace worker would end up with")
    ls.set_defaults(fn=do_list)
    ex = sub.add_parser("extract", help="write one resource out")
    ex.add_argument("archive")
    ex.add_argument("path", help="DIR/DIR/NAME.EXT as `list` prints it")
    ex.add_argument("out")
    ex.set_defaults(fn=do_extract)
    args = ap.parse_args(list(argv) if argv is not None else sys.argv[1:])
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
