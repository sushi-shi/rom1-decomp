"""rom1.graph.compdb - units.toml -> build/clangd/compile_commands.json.

    python3 -m rom1.graph.compdb            # (re)generate + coverage check
    python3 -m rom1.graph.compdb --check    # verify the existing file only

The clangd compilation database is ADDITIVE tooling that runs alongside the
matching build; it never touches it. The matching build compiles with MSVC
5.0's CL.EXE under wine, which clang-based consumers cannot invoke, so this
emits clang-cl driver entries that point clang at the era MSVC/MFC/DirectX
headers and ask it to *emulate* cl 11.00 (_MSC_VER 1100). Parse-only - no
wine, no CL.EXE.

Consumers: clangd (the .clangd file points CompileFlags.CompilationDatabase
at build/clangd/), rom1.tool.clang (per-TU extraction flags - a unit with
no entry silently falls back to bare MS flags, which is why generation always
ends with a coverage check THROUGH the consumer's own parser), the rom1.lsp
verbs, and rom1.verify.fingerprints.

Mechanics kept from the proven frozen generator (scripts/rom1-old/init/
clangd.py):
  * lowercase-symlink mirrors of the toolchain include dirs under
    build/clangd/inc-lower/ - the 1990s headers are ALL-UPPERCASE on disk
    (STRING.H, AFXWIN.H) but sources include them lowercase, and clang on
    case-sensitive Linux cannot find them otherwise; `/imsvc <mirror>` first,
    the real dirs after, DX before MSVC (VC5's own DDRAW.H is DirectX 3-era
    and would shadow the SDK's);
  * ONE shared flag set for every unit. The manifest's [flags] profiles differ
    only in /GX and /GR, which alter cl's EH tables and RTTI emission, not
    clang's parse/navigation - the frozen generator never mapped them and that
    uniform set is the proven state every fragment was extracted under;
  * write-if-changed: the labels edges depend on this file, so an unchanged
    payload must not bump its mtime (restat then stops the cascade anyway,
    but only after re-running 300 edges).

The ninja `compdb` edge (graph/emit.py) re-runs this on a units.toml or
module change. A TOOLCHAIN bump moves only $MSVC_DIR/$DXSDK_DIR, which ninja
cannot see - after re-pinning, run `python3 -m rom1.graph.compdb` once (the
mirror marker then rebuilds the symlink mirrors too).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from rom1.core.paths import BUILD, INCLUDE, REPO, VENDOR, dxsdk_dir, msvc_dir

OUT_DIR = BUILD / "clangd"
OUT_FILE = OUT_DIR / "compile_commands.json"
MIRROR_DIR = OUT_DIR / "inc-lower"

#: MSVC 5.0 == cl 11.00 == _MSC_VER 1100.
MSC_COMPAT = "11.00"
TARGET = "i386-pc-windows-msvc"

#: The matching build's environment: 32-bit Windows app, static ANSI/MBCS
#: MFC 4.2 (NAFXCW.LIB). _AFXDLL and _UNICODE are deliberately NOT defined.
DEFINES = ["/D_X86_", "/DWIN32", "/D_WINDOWS", "/D_MBCS"]


def resolve_include_dirs() -> tuple[Path, Path, str]:
    """(msvc_include, dx_include, provenance) for the era toolchain headers.

    Prefers the dev shell's $MSVC_DIR/$DXSDK_DIR; otherwise builds
    .#rom1-toolchain and reads the include dirs off the store path.
    """
    try:
        msvc_inc = msvc_dir() / "include"
        dx_inc = dxsdk_dir() / "Include"
        if msvc_inc.is_dir() and dx_inc.is_dir():
            return msvc_inc, dx_inc, "env ($MSVC_DIR / $DXSDK_DIR)"
    except RuntimeError:
        pass
    print("[compdb] MSVC_DIR/DXSDK_DIR not in env - "
          "running `nix build .#rom1-toolchain` ...", file=sys.stderr)
    try:
        out = subprocess.check_output(
            ["nix", "build", ".#rom1-toolchain", "--no-link",
             "--print-out-paths"], cwd=str(REPO), text=True,
        ).strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise SystemExit(
            "[compdb] ERROR: could not resolve the toolchain headers. Run "
            "inside `nix develop` (sets MSVC_DIR/DXSDK_DIR), or ensure "
            f"`nix build .#rom1-toolchain` works.\n  cause: {e}") from e
    root = Path(out[-1])
    msvc_inc, dx_inc = root / "msvc" / "include", root / "dx" / "Include"
    if not msvc_inc.is_dir() or not dx_inc.is_dir():
        raise SystemExit(f"[compdb] ERROR: toolchain at {root} is missing "
                         f"msvc/include or dx/Include.")
    return msvc_inc, dx_inc, f"nix build .#rom1-toolchain ({root})"


def build_lowercase_mirror(real: Path, mirror: Path) -> Path:
    """Recursive lowercase-symlink mirror of `real`, so <string.h> resolves.

    Every FOO.H under `real` gets a lowercase symlink `foo.h` (to the real,
    ABSOLUTE path) under `mirror`, preserving (lowercased) subdir structure.
    Rebuilt only when `real` changes (a `.src` marker guards it) so a
    toolchain bump does not leave dangling symlinks.
    """
    marker = mirror.parent / (mirror.name + ".src")
    if mirror.is_dir() and marker.is_file() and marker.read_text() == str(real):
        return mirror
    if mirror.exists():
        shutil.rmtree(mirror)
    for root, _dirs, files in os.walk(real):
        rel = os.path.relpath(root, real)
        low = mirror if rel == "." else mirror / rel.lower()
        low.mkdir(parents=True, exist_ok=True)
        for fn in files:
            link = low / fn.lower()
            if not link.exists():
                link.symlink_to(os.path.join(root, fn))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(real))
    return mirror


def base_flags(msvc_inc: Path, dx_inc: Path,
               msvc_low: Path, dx_low: Path) -> list[str]:
    """The clang-cl flag set shared by every unit.

    /imsvc marks the toolchain headers as SYSTEM includes (diagnostics inside
    the ancient MFC/CRT headers are silenced). Lowercase mirrors FIRST so a
    lowercase `#include <string.h>` resolves; the real (uppercase) dirs follow
    for exact-case includes; DX before MSVC in both tiers so the DX5 SDK wins
    over VC5's DirectX 3-era copies.
    """
    return [
        f"--target={TARGET}",
        f"-fms-compatibility-version={MSC_COMPAT}",
        "-fms-extensions",
        # `&Temporary()` is MSVC C4238, a nonstandard extension the retail
        # sources use; clang errors on it by default.
        "-Wno-address-of-temporary",
        # VC5 accepts SDK HRESULT macros such as DIERR_INSUFFICIENTPRIVS as
        # signed switch labels even when their `long` literal is unsigned.
        "-Wno-c++11-narrowing",
        # MFC's headers only parse under MSVC's lazy template semantics.
        "-fdelayed-template-parsing",
        "/imsvc", str(dx_low),
        "/imsvc", str(msvc_low),
        "/imsvc", str(dx_inc),
        "/imsvc", str(msvc_inc),
        # our own headers - NOT /imsvc, so diagnostics in our code surface.
        "/I", str(INCLUDE),
        # vendored SDK headers (vendor/<sdk>/, one dir deep).
        *[f for d in sorted(VENDOR.iterdir()) if d.is_dir()
          for f in ("/I", str(d))],
        *DEFINES,
    ]


def generate(quiet: bool = False) -> bool:
    """(Re)write the compdb from config/units.toml. Returns True if changed."""
    from rom1.manifest import units
    msvc_inc, dx_inc, provenance = resolve_include_dirs()
    msvc_low = build_lowercase_mirror(msvc_inc, MIRROR_DIR / "msvc")
    dx_low = build_lowercase_mirror(dx_inc, MIRROR_DIR / "dx")
    shared = base_flags(msvc_inc, dx_inc, msvc_low, dx_low)

    entries = [{
        "directory": str(REPO),
        "file": u["source"],
        # clang-cl driver form; clangd/clang parse it internally.
        "arguments": ["clang-cl", "/c", u["source"], *shared],
    } for u in units()]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entries, indent=2) + "\n"
    changed = not (OUT_FILE.exists()
                   and OUT_FILE.read_text(encoding="utf-8") == payload)
    if changed:
        OUT_FILE.write_text(payload, encoding="utf-8")
    if changed or not quiet:
        print(f"[compdb] {'wrote' if changed else 'unchanged'} "
              f"{OUT_FILE.relative_to(REPO)} ({len(entries)} units)")
    if not quiet:
        print(f"[compdb] include dirs ({provenance}):")
        print(f"    MSVC/MFC : {msvc_inc}")
        print(f"    DirectX  : {dx_inc}")
        print(f"    lowercase mirrors -> {MIRROR_DIR}")
        print("[compdb] clang-cl flags per unit:")
        print("    clang-cl /c <src> " + " ".join(shared))
    return changed


def dead_include_dirs(db: dict) -> list[str]:
    """The `/imsvc` and `/I` directories the stored entries name that are GONE.

    A toolchain re-pin moves $MSVC_DIR/$DXSDK_DIR, and ninja cannot see that -
    no edge depends on the environment - so the compdb keeps naming the OLD
    /nix/store path. Once that path is garbage-collected every entry is
    unusable, and unit COVERAGE (which only asks whether a source has a row)
    still reports 300/300. Answering "full coverage" for a database that
    cannot resolve <string.h> is the lie this closes.
    """
    wanted: set[str] = set()
    for args in db.values():
        args = list(args)
        for i, arg in enumerate(args[:-1]):
            if arg in ("/imsvc", "-imsvc", "/I", "-I"):
                wanted.add(args[i + 1])
    return sorted(d for d in wanted if not os.path.isdir(d))


def check(quiet: bool = False) -> list[str]:
    """Coverage through the CONSUMER's parser: every manifest unit must have
    an entry in rom1.tool.clang.compdb()'s dict - the exact join extraction
    performs, so a unit missing here is a unit that would silently fall back
    to bare MS flags. Returns the problems (empty = full coverage)."""
    from rom1.manifest import units
    from rom1.tool import clang
    db = clang.compdb()
    us = units()
    problems = []
    if not db:
        return [f"{OUT_FILE.relative_to(REPO)} is missing or unparsable - "
                f"EVERY unit would fall back to bare MS flags"]
    srcs = {}
    for u in us:
        srcs[os.path.realpath(str(REPO / u["source"]))] = u["unit"]
    missing = [unit for src, unit in srcs.items() if src not in db]
    problems += [f"unit '{u}' has NO compdb entry (bare-flag fallback)"
                 for u in sorted(missing)]
    stale = sorted(os.path.relpath(src, REPO) for src in db if src not in srcs)
    problems += [f"stale entry (not a manifest unit): {s}" for s in stale]
    dead = dead_include_dirs(db)
    problems += [f"include dir no longer exists: {d} - the toolchain moved; "
                 "re-run `python3 -m rom1.graph.compdb`" for d in dead]
    if not quiet or problems:
        print(f"[compdb] coverage: {len(us) - len(missing)}/{len(us)} units "
              f"have an entry ({len(stale)} stale, {len(dead)} dead include "
              "dir(s))")
    return problems


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the existing file only; write nothing")
    ap.add_argument("--quiet", action="store_true",
                    help="print only changes and problems (the ninja edge)")
    a = ap.parse_args()
    if not a.check:
        generate(a.quiet)
    problems = check(a.quiet)
    for p in problems:
        print(f"[compdb] {p}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
