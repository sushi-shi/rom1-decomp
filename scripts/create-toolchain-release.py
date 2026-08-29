#!/usr/bin/env python3
"""
create-toolchain-release.py  (RoM1 analysis bootstrap / MSVC 5.0 SP3)

Produces a self-contained rom1-toolchain tarball: Visual C++ 5.0 with Visual
Studio 97 Service Pack 3 applied (an analysis bootstrap, not the selected RoM1
compiler), ready to publish as a GitHub release. Once published, set the toolchain
sha256 in flake.nix to fetch that release instead of building from media.

Entry point:
  nix-shell scripts/create-toolchain-release.nix
  (fetches the VC5 ISO + SP3 + ninja, sets env vars, and runs this automatically)

Output:
  build/rom1-toolchain-vc50.tar.xz
    msvc/bin/      - cl.exe, c1.exe, c2.exe, link.exe, cvtres.exe, mspdb50.dll,
                     msdis100.dll, rc.exe, rcdll.dll (the last four from
                     SHAREDIDE/BIN, not VC/bin)
    msvc/include/  - C/C++ + MFC 4.2 headers
    msvc/lib/      - LIBCMT.LIB, NAFXCW.LIB, MFC42 static libs, import libs
    dx/{Include,Lib} - DirectX 5 SDK (archive.org `idx5sdk`, nested SFX)
    ninja/ninja.exe

VC++ 5.0 is PRE-MSI. The VS97 CDs are InstallShield with compressed CAB
cabinets, and SP3 ships as a self-extracting archive of WHOLE replacement
binaries. So this script:
  - uses ONLY `7z` to extract the ISO and the CABs (NO msiexec, NO Wine, NO
    xvfb, NO wineserver_settle, NO MSI File-table key matching),
  - applies SP3 by OVERLAYING its whole files over the base VC bin/ (and any
    lib it updates)
  - verifies the SP3 marker versions: link.exe 5.10.7303 and cvtres.exe
    5.00.1668 (the unique VS97-SP3 fingerprint from docs/compiler-detection.md)

The CAB extraction is unconditional `7z x` (7z handles InstallShield IS5/CAB
and Microsoft CAB); if a particular VS97 layer turns out to be an InstallShield
PackageForTheWeb / IS3 archive 7z cannot open, fall back to `cabextract` or
`unshield` (note it in docs/toolchain-vc50-sp3.md) - left as a TODO guard below.
"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

# ROM1_DIR is set by the nix-shell shellHook to $PWD (the repo root).
# Fallback for manual invocations where the script is run from its own directory.
ROM1_DIR = Path(os.environ.get("ROM1_DIR", str(Path(__file__).resolve().parent.parent)))

# Fixed mtime stamped on every tar entry for reproducible packaging.
# Rom1 retail (en) release: 1999-04-30 12:00:00 UTC (placeholder - adjust if a
# more exact date is wanted; only affects tar entry mtimes, not file contents).
RELEASE_EPOCH = 925473600

# SP3 marker versions for this bootstrap. RoM1 has no Rich header and its 5.02
# PE linker stamp rejects this payload for matching builds.
SP3_LINK_VERSION   = "5.10.7303"
SP3_CVTRES_VERSION = "5.00.1668"

# Static libs that MUST be present for Function-ID signature generation
# (docs/libraries-and-funcid.md): the static MT CRT and static release MFC 4.2.
REQUIRED_LIBS = ["LIBCMT.LIB", "NAFXCW.LIB"]


def log(msg: str) -> None:
    print(f"[release] {msg}", flush=True)


def run(cmd: list, *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, **kwargs)


def extract_7z(src: Path, dst: Path, *, iso: bool = False) -> None:
    """7z-extract an archive (ISO/CAB/zip/SFX). `iso=True` forces -tUDF|-tISO.
    """
    dst.mkdir(parents=True, exist_ok=True)
    cmd = ["7z", "x", "-y", f"-o{dst}", str(src)]
    # ISO: let 7z auto-detect (VS97 CDs are ISO9660/Joliet, not UDF); only pass
    # an explicit -t if auto-detect fails. 7z usually opens these fine bare.
    run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def extract_dxsdk(src: Path, dst: Path) -> None:
    """Extract idx5sdk.exe and the DX5SDK.EXE nested inside it."""
    outer = dst / "outer"
    inner = dst / "inner"
    extract_7z(src, outer)
    payload = next((p for p in outer.rglob("*")
                    if p.is_file() and p.name.lower() == "dx5sdk.exe"), None)
    if payload is None:
        raise SystemExit("DirectX 5 outer archive contains no DX5SDK.EXE")
    extract_7z(payload, inner)


def expand_all_cabs(root: Path, *, rounds: int = 3) -> None:
    """Recursively expand any *.cab / *.CAB found under `root`, in place.

    InstallShield/MSCAB media nest cabinets; a couple of rounds catch cabs that
    only appear after the first expansion. Files are unpacked next to their cab.
    """
    for _ in range(rounds):
        cabs = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".cab"]
        if not cabs:
            return
        for cab in cabs:
            out = cab.parent / (cab.stem + "_cab")
            extract_7z(cab, out)
            # avoid re-expanding the same cab next round
            try:
                cab.rename(cab.with_suffix(cab.suffix + ".done"))
            except OSError:
                pass


def file_version_strings(path: Path) -> str:
    """Best-effort version read: pull printable strings from a PE.
    """
    try:
        return subprocess.run(
            ["strings", "-a", str(path)], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        data = path.read_bytes()
        # extract ASCII runs >= 4
        out, run_chars = [], []
        for b in data:
            if 32 <= b < 127:
                run_chars.append(chr(b))
            else:
                if len(run_chars) >= 4:
                    out.append("".join(run_chars))
                run_chars = []
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Step 1 helpers: locate the VC tree inside the extracted CD
# ---------------------------------------------------------------------------

def find_vc_bin(root: Path) -> Path | None:
    """Find the VC bin directory (the one containing cl.exe) in the extracted CD.

    VS97 lays the compiler under .../DevStudio/VC/bin (also VC/include, VC/lib,
    VC/mfc/{include,lib,src}). The CD may store it compressed - run
    expand_all_cabs() before calling this. Returns the bin/ dir.
    """
    for cl in root.rglob("CL.EXE"):
        if cl.parent.name.lower() == "bin":
            return cl.parent
    # case-insensitive fallback
    for p in root.rglob("*"):
        if p.is_file() and p.name.lower() == "cl.exe" and p.parent.name.lower() == "bin":
            return p.parent
    return None


def find_named(root: Path, name: str) -> Path | None:
    """First file under root whose name matches `name` case-insensitively."""
    low = name.lower()
    for p in root.rglob("*"):
        if p.is_file() and p.name.lower() == low:
            return p
    return None


# ---------------------------------------------------------------------------
# Step 1: extract VC++ 5.0 base from the VS97 Disc 3 ISO
# ---------------------------------------------------------------------------

def step1_vc5_base(work: Path, stage: Path) -> Path:
    vc5_iso = Path(os.environ["VC5_ISO"])

    log("Extracting VC++ 5.0 (VS97 Disc 3) ISO with 7z (no msiexec - pre-MSI media) ...")
    iso_dir = work / "vc5-iso"
    extract_7z(vc5_iso, iso_dir, iso=True)

    log("Expanding InstallShield/CAB cabinets ...")
    expand_all_cabs(iso_dir)

    vc_bin = find_vc_bin(iso_dir)
    if not vc_bin:
        log("ERROR: cl.exe not found in the VC5 CD after 7z extract + cab expand.")
        log("  - Confirm VC5_ISO is the VS97 *Disc 3* (Visual C++) image.")
        log("  - If the CD uses InstallShield IS3/PackageForTheWeb that 7z cannot")
        log("    open, expand with `cabextract`/`unshield` (see docs).")
        for d in sorted({p.parent for p in iso_dir.rglob('*.EXE')})[:20]:
            print(f"    {d}")
        raise SystemExit(1)
    vc_dir = vc_bin.parent
    log(f"Found VC at: {vc_dir}")

    stage_msvc = stage / "msvc"
    for sub in ("bin", "include", "lib"):
        src = vc_dir / sub
        if not src.is_dir():
            # case-insensitive resolve
            src = next((c for c in vc_dir.iterdir()
                        if c.is_dir() and c.name.lower() == sub), src)
        if src.is_dir():
            shutil.copytree(str(src), str(stage_msvc / sub), dirs_exist_ok=True)
            log(f"  staged msvc/{sub} from {src}")

    # MFC 4.2 lives under VC/mfc/{include,lib,src}; the static MFC release lib
    # NAFXCW.LIB is in mfc/lib. Merge mfc/include -> include, mfc/lib -> lib so
    # the standard search paths see them (the SP3 brief calls for LIBCMT.LIB +
    # NAFXCW.LIB co-located in lib/ for FID).
    mfc_dir = next((c for c in vc_dir.iterdir()
                    if c.is_dir() and c.name.lower() == "mfc"), None)
    if mfc_dir:
        for sub, dst in (("include", "include"), ("lib", "lib")):
            s = next((c for c in mfc_dir.iterdir()
                      if c.is_dir() and c.name.lower() == sub), None)
            if s:
                shutil.copytree(str(s), str(stage_msvc / dst), dirs_exist_ok=True)
                log(f"  merged mfc/{sub} -> msvc/{dst}")
        # keep the MFC sources too (handy for matching inlined MFC bodies)
        src_dir = next((c for c in mfc_dir.iterdir()
                        if c.is_dir() and c.name.lower() == "src"), None)
        if src_dir:
            shutil.copytree(str(src_dir), str(stage_msvc / "mfc-src"), dirs_exist_ok=True)
            log("  staged mfc/src -> msvc/mfc-src")
    else:
        log("WARNING: VC/mfc not found - NAFXCW.LIB may be missing (needed for FID).")

    # cl.exe IMPORTS mspdb50.dll at LOAD time (it is in cl's PE import table, not
    # just a /Zi-time dependency) and it ships under SHAREDIDE/BIN, NOT VC/bin - so
    # without this copy cl.exe fails to load under Wine (c0000135) and silently
    # produces no .obj. mspdb50.dll itself only imports MSVCRT + KERNEL32 (both Wine
    # builtins). Verified: `wine cl /c hello.cpp` -> i386 COFF .obj once present.
    mspdb = find_named(iso_dir, "mspdb50.dll")
    if mspdb:
        shutil.copy2(str(mspdb), str(stage_msvc / "bin" / mspdb.name))
        log(f"  bundled {mspdb.name} from {mspdb} (cl.exe imports it)")
    else:
        log("WARNING: MSPDB50.DLL not found under the ISO - cl.exe will fail to load!")

    return stage_msvc


# ---------------------------------------------------------------------------
# Step 2: apply VS97 Service Pack 3 (overlay whole replacement files)
#
# A self-extracting archive of WHOLE files. We extract it with 7z and copy
# each updated binary over the base. SP3 replaces the versioned tools
# (cl/c1/c1xx/c2/link/cvtres/mspdb*); it does NOT rewrite the whole tree,
# so we overlay onto bin/ (and lib/ for any updated libs) by name.
# ---------------------------------------------------------------------------

# Tool binaries VS97 SP3 ships WHOLE and that we overlay onto msvc/bin.
#
# What SP3 actually carries (verified against the SP3 cab layout):
#   - all/vc/bin/cvtres.exe              language-neutral; reports 5.00.1668 (the
#                                        unique byte-match marker for Rom1)
#   - <lang>/vc/bin/{c1.dll,c1xx.dll,    the compiler back-end + linker (per-
#                    c2.exe,cvpack.exe,  language; we always pick the ENGLISH
#                    link.exe}           "enu" variant - see SP3_LANG below)
# SP3 does NOT ship cl.exe (the driver stays RTM 11.00.7022), nor mspdb50.dll
# (the base SHAREDIDE MSPDB50.DLL is what SP3 link references), nor the static
# libs as bin files (those are handled by the *.lib overlay below). Note the
# compiler front-ends are c1.DLL/c1xx.DLL (not .exe) in VC5.
SP3_BIN_OVERLAY = [
    "cvtres.exe", "link.exe", "c1.dll", "c1xx.dll", "c2.exe", "cvpack.exe",
]

# SP3 ships the language-specific bin tools under per-language dirs
# (.../VS97_SP3/{all,enu,deu,jpn}/vc/bin/...). We want the English build for a
# deterministic, byte-match result, so prefer a path containing "/enu/" (then
# "/all/"); never let rglob order silently pick the German/Japanese variant.
SP3_LANG_PREFERENCE = ("/enu/", "/all/")


def step2_apply_sp3(work: Path, stage_msvc: Path) -> None:
    sp3_zip = os.environ.get("VS97_SP3_ZIP")
    sp3_iso = os.environ.get("VS97_SP3_ISO")
    src = Path(sp3_zip) if sp3_zip else (Path(sp3_iso) if sp3_iso else None)
    if not src:
        log("WARNING: no VS97_SP3_ZIP/VS97_SP3_ISO set - cannot reproduce the "
            "declared SP3 bootstrap payload.")
        return

    log(f"Extracting VS97 SP3 ({src.name}) with 7z ...")
    sp3_dir = work / "sp3"
    extract_7z(src, sp3_dir, iso=src.suffix.lower() == ".iso")
    expand_all_cabs(sp3_dir)

    sp3_files = [p for p in sp3_dir.rglob("*") if p.is_file()]
    bin_dir = stage_msvc / "bin"
    lib_dir = stage_msvc / "lib"

    def pick_lang(cands: list) -> Path | None:
        """Pick the preferred-language candidate (English) deterministically.

        SP3 ships c1/c1xx/c2/cvpack/link under {all,enu,deu,jpn}/vc/bin; the
        base media + retail game are English, so we must overlay the *enu*
        build, not whatever rglob happens to return first.
        """
        if not cands:
            return None
        for pref in SP3_LANG_PREFERENCE:
            for c in cands:
                if pref in str(c).replace(os.sep, "/").lower():
                    return c
        return sorted(cands)[0]  # stable fallback

    def overlay_one(src: Path, dst_dir: Path) -> str:
        """Copy `src` into `dst_dir`, REPLACING any case-insensitive match.

        The base media store names UPPERCASE (CVTRES.EXE) while SP3 cabs are
        lowercase (cvtres.exe); on a case-sensitive FS a naive copy would leave
        BOTH and the stale RTM file would win lookups. So delete the existing
        differently-cased file first, then write the SP3 name. Returns the final
        relative name for logging.
        """
        dst_dir.mkdir(parents=True, exist_ok=True)
        existing = next((p for p in dst_dir.glob("*")
                         if p.name.lower() == src.name.lower()), None)
        if existing and existing.name != src.name:
            existing.unlink()
        shutil.copy2(str(src), str(dst_dir / src.name))
        return src.name

    replaced = 0
    for target in SP3_BIN_OVERLAY:
        cands = [p for p in sp3_files if p.name.lower() == target.lower()]
        cand = pick_lang(cands)
        if not cand:
            log(f"  SP3 overlay  bin/{target}: NOT FOUND in SP3 (skipped)")
            continue
        name = overlay_one(cand, bin_dir)
        replaced += 1
        log(f"  SP3 overlay  bin/{name}  <- {cand.parent.name}/{cand.name}")

    # SP3 also refreshes the static/import libs (CRT + MFC42); overlay every
    # *.lib it carries that we already staged (don't introduce libs that were
    # not on the base). Replace case-insensitively so we update the existing
    # uppercase lib in place rather than dropping a lowercase duplicate.
    for cand in sp3_files:
        if cand.suffix.lower() != ".lib":
            continue
        existing = next((p for p in lib_dir.glob("*")
                         if p.name.lower() == cand.name.lower()), None) if lib_dir.is_dir() else None
        if existing:
            shutil.copy2(str(cand), str(existing))
            replaced += 1
            log(f"  SP3 overlay  lib/{existing.name}")

    log(f"SP3 overlay: replaced/added {replaced} file(s).")


# ---------------------------------------------------------------------------
# MSDIS100.DLL - the VC5 disassembler engine. The SP3 link.exe (5.10.7303)
# imports it at LOAD time (it is in link.exe's PE import table - used by the
# `link /dump /disasm` path), and like MSPDB50.DLL it ships under SHAREDIDE/BIN,
# NOT VC/bin - so the VC/bin copytree in step1 misses it and link.exe then fails
# to load under wine (c0000135). Pull it from wherever it sits across the base
# ISO + SP3 extracts (both live under `work`) into msvc/bin. (For tarballs built
# before this fix, scripts/rom1/build/msdis_stub.py supplies an export-only stub
# at link time so `rom1 link` still works - bundling the real DLL additionally
# makes `link /dump /disasm` functional.)
# ---------------------------------------------------------------------------

def bundle_msdis(work: Path, stage_msvc: Path) -> None:
    # msvcp50.dll rides along: the REAL msdis100.dll imports the VC5 C++
    # runtime at load (the old export-only stub did not), so link.exe cannot
    # load without both beside it (VC/REDIST/MSVCP50.DLL on the same disc).
    bin_dir = stage_msvc / "bin"
    for name in ("msdis100.dll", "msvcp50.dll"):
        if any(p.name.lower() == name for p in bin_dir.glob("*")):
            log(f"  {name} already in msvc/bin")
            continue
        src = find_named(work, name)
        if src:
            shutil.copy2(str(src), str(bin_dir / src.name))
            log(f"  bundled {src.name} from {src} (link.exe load-time need)")
        else:
            log(f"WARNING: {name} not found in the VC5 media - link.exe may "
                "fail to load under wine (c0000135).")


def bundle_rc(work: Path, stage_msvc: Path) -> None:
    """RC.EXE + RCDLL.DLL - the era resource compiler (.rc -> .res).

    Ships under SHAREDIDE/BIN like MSPDB50/MSDIS100, so the VC/bin copytree in
    step1 misses it. RC.EXE is a thin driver that imports RCDLL.DLL (the actual
    compiler) at load time - both must land in msvc/bin or `wine rc` fails with
    c0000135. The rebuild's resource step drives this real rc.exe; there is no
    python fallback."""
    bin_dir = stage_msvc / "bin"
    for name in ("rc.exe", "rcdll.dll"):
        if any(p.name.lower() == name for p in bin_dir.glob("*")):
            log(f"  {name} already in msvc/bin")
            continue
        src = find_named(work, name)
        if src:
            shutil.copy2(str(src), str(bin_dir / src.name))
            log(f"  bundled {src.name} from {src} (resource compiler)")
        else:
            log(f"WARNING: {name} not found in the VC5 media - the resource "
                "step has NO tool without it (check the SHAREDIDE cabs; it may "
                "require the VS97 IDE disc).")


def verify_sp3(stage_msvc: Path, *, fatal: bool) -> None:
    """Verify the SP3 marker versions + the FID-required static libs.

    The gate that stops a wrong-toolchain tarball shipping silently.
    cvtres 5.00.1668 is the unique SP3 fingerprint.
    """
    bin_dir = stage_msvc / "bin"
    lib_dir = stage_msvc / "lib"
    ok = True

    link = next((p for p in bin_dir.glob("*") if p.name.lower() == "link.exe"), None)
    if link:
        s = file_version_strings(link)
        if SP3_LINK_VERSION in s:
            log(f"link.exe is SP3 ({SP3_LINK_VERSION}) OK")
        else:
            log(f"SP3 CHECK: link.exe does not report {SP3_LINK_VERSION} "
                "(version string not found - may still be RTM 5.10.7303-pre/SP2)")
            ok = False
    else:
        log("SP3 CHECK: link.exe missing from msvc/bin"); ok = False

    cvtres = next((p for p in bin_dir.glob("*") if p.name.lower() == "cvtres.exe"), None)
    if cvtres:
        s = file_version_strings(cvtres)
        if SP3_CVTRES_VERSION in s:
            log(f"cvtres.exe is SP3 ({SP3_CVTRES_VERSION}) OK  <- the unique SP3 marker")
        else:
            log(f"SP3 CHECK: cvtres.exe does not report {SP3_CVTRES_VERSION} "
                "(the byte-match fingerprint) - SP3 overlay may not have taken")
            ok = False
    else:
        log("SP3 CHECK: cvtres.exe missing from msvc/bin"); ok = False

    # link.exe's load-time MSDIS100.DLL import. Non-fatal: msdis_stub.py supplies a
    # stub fallback at link time, so its absence does not block linking - but a
    # complete tarball should carry the real DLL.
    msdis = next((p for p in bin_dir.glob("*") if p.name.lower() == "msdis100.dll"), None)
    if msdis:
        log("MSDIS100.DLL present OK  <- link.exe load-time import")
    else:
        log("NOTE: MSDIS100.DLL absent from msvc/bin - link.exe will use the "
            "msdis_stub.py fallback (linking works; `link /dump /disasm` won't).")

    # The resource compiler pair. No fallback exists in the rebuilt tree, so a
    # tarball without it cannot compile .rsrc - loud, but not an SP3 marker.
    for name in ("rc.exe", "rcdll.dll"):
        if next((p for p in bin_dir.glob("*") if p.name.lower() == name), None):
            log(f"{name} present OK  <- resource compiler")
        else:
            log(f"NOTE: {name} absent from msvc/bin - the resource step has no tool.")
    if next((p for p in bin_dir.glob("*") if p.name.lower() == "msvcp50.dll"), None):
        log("msvcp50.dll present OK  <- msdis100.dll load-time import")
    else:
        log("NOTE: msvcp50.dll absent - the real msdis100.dll cannot load.")

    for libname in REQUIRED_LIBS:
        found = next((p for p in lib_dir.glob("*")
                      if p.name.lower() == libname.lower()), None) if lib_dir.is_dir() else None
        if found:
            log(f"FID lib {libname} present OK")
        else:
            log(f"LIB CHECK: {libname} missing from msvc/lib (needed for Function-ID)")
            ok = False

    if not ok and fatal:
        raise SystemExit(
            "SP3 bootstrap failed its identity/lib verification. "
            "Expected link 5.10.7303 + cvtres 5.00.1668 "
            "and LIBCMT.LIB + NAFXCW.LIB in lib/. Aborting rather than ship a wrong "
            "toolchain."
        )


# ---------------------------------------------------------------------------
# Step 3: exact DirectX 5 SDK (fetched by create-toolchain-release.nix)
# ---------------------------------------------------------------------------

def step3_dxsdk(work: Path, stage: Path) -> None:
    dxsdk_exe = os.environ.get("DXSDK_EXE")
    stage_dx = stage / "dx"
    if not dxsdk_exe:
        raise SystemExit("DXSDK_EXE unset: exact DirectX 5 SDK is required")

    log("Extracting DirectX 5 SDK ...")
    dx_work = work / "dxsdk"
    dx_work.mkdir(parents=True, exist_ok=True)
    extract_dxsdk(Path(dxsdk_exe), dx_work)

    # The nested payload stores the canonical headers/import libs at
    # cdrom/sdk/{inc,lib}; choose those exact roots, never a sample directory.
    def pick_top(name: str, must_contain: str) -> Path | None:
        cands = [p for p in dx_work.rglob("*")
                 if p.is_dir() and p.name.lower() == name]
        if not cands:
            return None
        with_marker = [p for p in cands
                       if any(c.name.lower() == must_contain for c in p.iterdir())]
        pool = with_marker or cands
        return min(pool, key=lambda p: len(p.relative_to(dx_work).parts))

    inc = pick_top("inc", "ddraw.h")
    lib = pick_top("lib", "ddraw.lib")
    if inc:
        shutil.copytree(str(inc), str(stage_dx / "Include"), dirs_exist_ok=True)
        log(f"  DX5 Include <- {inc.relative_to(dx_work)}")
    if lib:
        shutil.copytree(str(lib), str(stage_dx / "Lib"), dirs_exist_ok=True)
        log(f"  DX5 Lib     <- {lib.relative_to(dx_work)}")
    if not inc or not lib:
        raise SystemExit("DirectX 5 payload missing cdrom/sdk/inc or cdrom/sdk/lib")
    log("DirectX 5 SDK staged exactly.")


# ---------------------------------------------------------------------------
# Step 4: ninja.exe
# ---------------------------------------------------------------------------

def step4_ninja(work: Path, stage: Path) -> None:
    ninja_zip = os.environ.get("NINJA_WIN_ZIP")
    ninja_dir = stage / "ninja"
    ninja_dir.mkdir(parents=True, exist_ok=True)
    if not ninja_zip:
        log("NINJA_WIN_ZIP unset - skipping ninja.exe (build driver). TODO: set it.")
        return
    log("Extracting ninja.exe ...")
    run(["7z", "e", str(ninja_zip), "ninja.exe", f"-o{ninja_dir}", "-y"],
        stdout=subprocess.DEVNULL, check=False)
    if not (ninja_dir / "ninja.exe").exists():
        log("WARNING: ninja.exe not found in zip")


# ---------------------------------------------------------------------------
# Step 5: Package
# ---------------------------------------------------------------------------

def step5_package(work: Path, stage: Path, output: Path) -> None:
    log(f"Packaging -> {output} ...")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reproducibility: the staged file *contents* are deterministic (7z extract
    # of pinned media). Only tar metadata is nondeterministic, so normalise it:
    #   --sort=name       stable entry order
    #   --mtime=@...      fix every entry timestamp to RELEASE_EPOCH
    #   --owner/--group/--numeric-owner  drop the building user's identity
    #   --format=gnu      avoid pax atime/ctime extended headers
    # With these, the same media + pinned tooling produce a byte-identical tarball.
    run([
        "tar",
        "--sort=name",
        "--format=gnu",
        "--owner=0", "--group=0", "--numeric-owner",
        f"--mtime=@{RELEASE_EPOCH}",
        "--transform", r"s|^\.|rom1-toolchain-vc50|",
        "-C", str(stage),
        "-cJf", str(output), ".",
    ])

    h = hashlib.sha256()
    with output.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    digest = h.hexdigest()
    size_mb = output.stat().st_size / (1024 ** 2)

    print()
    log("Done!")
    print(f"  Output: {output}  ({size_mb:.1f} MB)")
    print(f"  SHA256: {digest}")
    print()
    print("Next steps:")
    print(f"  1. gh release upload toolchain-vc50-sp3 {output} "
          "--repo sushi-shi/rom1-decomp --clobber")
    print( "  2. In flake.nix, replace the rom1-toolchain fetchurl sha256 with:")
    print(f'       sha256 = "{digest}";')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    output = Path(os.environ.get(
        "OUTPUT",
        str(ROM1_DIR / "build" / "rom1-toolchain-vc50.tar.xz"),
    ))
    work = Path(os.environ.get(
        "WORK_DIR",
        str(ROM1_DIR / "binaries" / ".release-work"),
    ))
    stage = work / "stage"

    work.mkdir(parents=True, exist_ok=True)
    stage.mkdir(parents=True, exist_ok=True)

    log(f"Work dir: {work}")
    log(f"Output:   {output}")
    print()

    try:
        stage_msvc = step1_vc5_base(work, stage)
        step2_apply_sp3(work, stage_msvc)
        bundle_msdis(work, stage_msvc)   # link.exe load-time import (SHAREDIDE/BIN)
        bundle_rc(work, stage_msvc)      # resource compiler pair (SHAREDIDE/BIN)
        # fatal only when SP3 was supplied; without SP3 we already warned loudly.
        verify_sp3(stage_msvc, fatal=bool(os.environ.get("VS97_SP3_ZIP")
                                          or os.environ.get("VS97_SP3_ISO")))
        step3_dxsdk(work, stage)
        step4_ninja(work, stage)
        step5_package(work, stage, output)
    finally:
        log("Cleaning up work dir ...")
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
