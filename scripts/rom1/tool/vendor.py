"""Verify the pinned Smacker header patch and RoM1's complete imported ABI.

The closest public SDK header is 3.2f.  This command verifies its provenance,
the one-line 3.1L compatibility patch, every decorated import in ALLODS.EXE,
and the identity/export surface of the retail 3.1L runtime DLL.  It deliberately
does not call the unobserved portion of the 3.1L SDK header byte-exact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import struct
from io import StringIO
from pathlib import Path

from rom1.core.paths import REPO, retail_exe
from rom1.core.pe import Pe


ROOT = REPO / "vendor/smacker-3.1l"
ORIG = ROOT / "orig"
ABI = ROOT / "retail_imports.tsv"
UPSTREAM_COMMIT = "f42d146c164f264d22e593827a2a028e45fd83d6"
ORIG_SHA256 = {
    "rad.h": "298e860962567d5af2556e6c7f8db42f43ee1ef328cf5deb1efd9a0b1941ad71",
    "smack.h": "1f7bc112b8a09a37c7635540a5aed516c65b891d2e45142b19952ad21961699b",
}
RUNTIME_SHA256 = "79ff40e84fd339930ad358768ad4408e6280074a67e3b1733434d2294b0f5bc5"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cstring(pe: Pe, rva: int) -> str:
    out = bytearray()
    while True:
        byte = pe.read(rva + len(out), 1)
        if not byte:
            raise ValueError(f"unterminated/missing string at RVA 0x{rva:x}")
        if byte == b"\0":
            return out.decode("ascii")
        out += byte


def smack_imports(pe: Pe) -> list[dict[str, str]]:
    """Return the named SMACKW32 imports in original thunk order."""
    import_rva, _size = pe.directories[1]
    result: list[dict[str, str]] = []
    for index in range(4096):
        raw = pe.read(import_rva + index * 20, 20)
        if raw is None:
            raise ValueError("truncated import directory")
        original, _stamp, _chain, name_rva, first = struct.unpack("<IIIII", raw)
        if not any((original, name_rva, first)):
            break
        if cstring(pe, name_rva).lower() != "smackw32.dll":
            continue
        thunk = original or first
        for slot in range(4096):
            value = struct.unpack("<I", pe.read(thunk + slot * 4, 4))[0]
            if value == 0:
                break
            if value & 0x80000000:
                raise ValueError("RoM1 imports SMACKW32 by ordinal unexpectedly")
            hint = struct.unpack("<H", pe.read(value, 2))[0]
            symbol = cstring(pe, value + 2)
            match = re.fullmatch(r"_([A-Za-z0-9_]+)@(\d+)", symbol)
            if not match:
                raise ValueError(f"unexpected undecorated Smacker import {symbol!r}")
            result.append({"hint": f"0x{hint:04x}", "symbol": symbol,
                           "function": match.group(1),
                           "stack_bytes": match.group(2)})
    if not result:
        raise ValueError("retail executable has no named SMACKW32 imports")
    return result


def exports(pe: Pe) -> set[str]:
    export_rva, _size = pe.directories[0]
    raw = pe.read(export_rva, 40)
    if raw is None:
        raise ValueError("runtime has no readable export directory")
    fields = struct.unpack("<IIHHIIIIIII", raw)
    number_of_names, address_of_names = fields[7], fields[9]
    result = set()
    for index in range(number_of_names):
        name_rva = struct.unpack(
            "<I", pe.read(address_of_names + index * 4, 4))[0]
        result.add(cstring(pe, name_rva))
    return result


def render_abi(rows: list[dict[str, str]], exe_hash: str) -> str:
    out = StringIO()
    out.write(f"# retail_sha256={exe_hash}\n")
    writer = csv.DictWriter(out, ("hint", "symbol", "function", "stack_bytes"),
                            delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def verify_headers(rows: list[dict[str, str]]) -> None:
    for name, expected in ORIG_SHA256.items():
        actual = sha256((ORIG / name).read_bytes())
        if actual != expected:
            raise ValueError(f"orig/{name}: expected upstream sha256 {expected}, got {actual}")

    original = (ORIG / "smack.h").read_text()
    expected = original.replace('#define SMACKVERSION "3.2f"',
                                '#define SMACKVERSION "3.1L"', 1)
    if expected == original:
        raise ValueError("upstream smack.h lost its 3.2f version witness")
    if (ROOT / "smack.h").read_text() != expected:
        raise ValueError("smack.h is not the exact admitted 3.1L patch")
    rad_original = (ORIG / "rad.h").read_text()
    rad_marker = """  void __inline LockedIncrementFunc(void PTR4* var) {
    __asm {
"""
    rad_replacement = """#if defined(__clang__) && defined(ROM1_EMIT_META)
  void __inline LockedIncrementFunc(void PTR4* var) { ++(*((u32*)var)); }
  void __inline LockedDecrementFunc(void PTR4* var) { --(*((u32*)var)); }
#else
  void __inline LockedIncrementFunc(void PTR4* var) {
    __asm {
"""
    rad_expected = rad_original.replace(rad_marker, rad_replacement, 1)
    rad_tail = """       lock dec [eax]
    }
  }

#else
"""
    rad_tail_replacement = """       lock dec [eax]
    }
  }
#endif

#else
"""
    rad_expected = rad_expected.replace(rad_tail, rad_tail_replacement, 1)
    # The materialized patch normalizes the upstream file's redundant final
    # blank line; retain one canonical POSIX newline in the include tree.
    rad_expected = rad_expected.rstrip() + "\n"
    if rad_expected == rad_original or (ROOT / "rad.h").read_text() != rad_expected:
        raise ValueError("rad.h is not the exact admitted Clang metadata patch")

    header = expected
    for row in rows:
        name = re.escape(row["function"])
        match = re.search(
            rf"^\s*RADEXPFUNC[^\n;]*\bRADEXPLINK\s+{name}\s*\(([^;]*)\);",
            header, re.MULTILINE)
        if not match:
            raise ValueError(f"no single-line prototype for {row['function']}")
        args = match.group(1).strip()
        count = 0 if args == "void" else len([arg for arg in args.split(",") if arg.strip()])
        header_bytes = count * 4
        if header_bytes != int(row["stack_bytes"]):
            raise ValueError(
                f"{row['function']}: header implies @{header_bytes}, retail imports "
                f"@{row['stack_bytes']}")


def runtime_default() -> Path | None:
    value = os.environ.get("ROM1_RUNTIME")
    if not value:
        return None
    path = Path(value)
    return path / "SMACKW32.DLL" if path.is_dir() else path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=retail_exe())
    parser.add_argument("--runtime", type=Path, default=runtime_default())
    parser.add_argument("--write", action="store_true",
                        help="admit the executable-derived retail_imports.tsv")
    args = parser.parse_args(argv)
    try:
        exe = Pe(args.exe)
        rows = smack_imports(exe)
        payload = render_abi(rows, sha256(exe.data))
        if args.write:
            ABI.write_text(payload)
        elif not ABI.is_file() or ABI.read_text() != payload:
            raise ValueError("retail_imports.tsv drift (inspect and pass --write to admit)")
        verify_headers(rows)

        if args.runtime is None:
            raise ValueError("runtime unavailable: pass --runtime or enter nix develop")
        runtime_data = args.runtime.read_bytes()
        actual_hash = sha256(runtime_data)
        if actual_hash != RUNTIME_SHA256:
            raise ValueError(f"runtime sha256 {actual_hash}, expected {RUNTIME_SHA256}")
        if b"*** Smacker Version: 3.1L***" not in runtime_data:
            raise ValueError("runtime lacks its embedded Smacker 3.1L identity")
        missing = {row["symbol"] for row in rows} - exports(Pe(args.runtime))
        if missing:
            raise ValueError("runtime lacks imports: " + ", ".join(sorted(missing)))
    except (OSError, ValueError, IndexError, struct.error) as error:
        print(f"[vendor] FAIL: {error}")
        return 1
    print(f"[vendor] exact: {len(rows)} retail imports; header ABI and 3.1L runtime verified")
    print(f"[vendor] upstream edgeforce/radtools@{UPSTREAM_COMMIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
