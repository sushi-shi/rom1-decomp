#!/usr/bin/env python3
"""Build the exact RoM1 VC5 SP2 + DirectX 5 toolchain release.

The SP2 payload is an overlay, not a standalone compiler.  This builder starts
from the pinned Visual Studio 97 Professional Disc 3 RTM tree and applies only
the English and language-neutral files from the official expanded VSSP2 tree.
It deliberately never uses the convenient SP3 bootstrap as a base.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


REPO = Path(os.environ.get(
    "ROM1_DIR", str(Path(__file__).resolve().parent.parent)))
HELPERS_PATH = Path(__file__).with_name("create-toolchain-release.py")
SPEC = importlib.util.spec_from_file_location("rom1_release_helpers", HELPERS_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit(f"cannot load release helpers: {HELPERS_PATH}")
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)

RELEASE_EPOCH = 925473600
RELEASE_ROOT = "rom1-toolchain-vc50-sp2-dx5"

SOURCE_IDENTITIES = {
    "vc5-rtm": {
        "url": "https://archive.org/download/microsoft-visual-studio-97-professional-edition-disc-3/Microsoft%20Visual%20Studio%2097%20Professional%20Edition%20-%20Disc%203.iso",
        "size": "655605760",
        "md5": "bf71b8fc2d23c5de13734b189dc341cb",
        "sha1": "a3ade9b0681ffab34f058a7991f6b7aa25d342e1",
        "sha256": "99101fb01f564ba9cc50cbcbf862c334cd1be16a2e8c277cb81f9a500cb6413f",
    },
    "vc5-sp2": {
        "url": "https://archive.org/download/vc-tech-pre/VC_TECH_PRE.ISO",
        "size": "633636864",
        "md5": "f421948d6515123c141aefe7290b74b7",
        "sha1": "81b80cca71229ae7a7be09dc21f699c4a1dc3588",
        "sha256": "da848cf6902b9461c11503370a26f26bc30df8b544a8d14e8eeeb4110339fd75",
    },
}

SP2_TOOL_SHA256 = {
    "c1.dll": "7f12a4a889c5a0277f12c391ca462657dc81ef7be769faf629331bd117983d5d",
    "c1xx.dll": "8b66d3f14035bfa228e79d45481318457594f65ed91f87319d23932372857d8b",
    "c2.exe": "592c65eea2e159a8b7bf61fb20ed12fc0dfdb3c5b7179267d34634aa7a2dc6e4",
    "cvpack.exe": "62f51b0d705d10426d5b38fc6340859d0bfc829d9d93f27d12a6caa8a2ebe6c6",
    "link.exe": "e28424d3eefcdd96ecc8c3fe38d0fad3d33077c62026f7774eda90784d0eb4d9",
    "mspdb50.dll": "730497a2cc447ad0ea91c52ed9aa1b9d21572f4ca37ce686937946c5a98f7f8c",
    "msdis100.dll": "2abf240e688910b903065c2c26321d1dc3aecb82186fdbee113a01c9ef3d8943",
}

SP2_TOOL_VERSIONS = {
    "c1.dll": "11.0.0.7113",
    "c1xx.dll": "11.0.0.7149",
    "c2.exe": "11.0.0.7153",
    "cvpack.exe": "5.0.0.7113",
    "link.exe": "5.2.0.7132",
    "mspdb50.dll": "5.0.0.7113",
    "msdis100.dll": "1.0.0.7103",
}


def log(message: str) -> None:
    print(f"[sp2-release] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_file_version(path: Path) -> str:
    data = path.read_bytes()
    offset = data.find(struct.pack("<I", 0xFEEF04BD))
    if offset < 0 or offset + 16 > len(data):
        return ""
    _sig, _struct, ms, ls = struct.unpack_from("<IIII", data, offset)
    parts = (ms >> 16, ms & 0xffff, ls >> 16, ls & 0xffff)
    while len(parts) > 2 and parts[-1] == 0:
        parts = parts[:-1]
    return ".".join(map(str, parts))


def find_ci(root: Path, name: str, *, directory: bool | None = None) -> Path | None:
    if not root.is_dir():
        return None
    wanted = name.lower()
    for child in root.iterdir():
        if child.name.lower() != wanted:
            continue
        if directory is None or child.is_dir() == directory:
            return child
    return None


def require_dir(root: Path, relative: str) -> Path:
    current = root
    for part in Path(relative).parts:
        found = find_ci(current, part, directory=True)
        if found is None:
            raise SystemExit(f"SP2 payload is missing {relative}")
        current = found
    return current


def overlay_tree(src_root: Path, dst_root: Path, source_label: str,
                 rows: list[dict[str, str]]) -> None:
    """Overlay a tree with Windows-style case-insensitive replacement."""
    dst_root.mkdir(parents=True, exist_ok=True)
    for src in sorted((p for p in src_root.rglob("*") if p.is_file()),
                      key=lambda p: str(p.relative_to(src_root)).lower()):
        rel = src.relative_to(src_root)
        dst_parent = dst_root
        for part in rel.parts[:-1]:
            existing_dir = find_ci(dst_parent, part, directory=True)
            if existing_dir is None:
                existing_dir = dst_parent / part
                existing_dir.mkdir(parents=True, exist_ok=True)
            dst_parent = existing_dir
        existing = find_ci(dst_parent, rel.name, directory=False)
        if existing is not None:
            destination = existing
        else:
            destination = dst_parent / rel.name
        shutil.copy2(src, destination)
        rows.append({
            "destination": str(destination.relative_to(dst_root.parent)),
            "source": f"{source_label}/{rel.as_posix()}",
            "size": str(src.stat().st_size),
            "sha256": sha256(src),
        })


def locate_sp2(work: Path) -> tuple[Path, Path | None]:
    expanded = os.environ.get("VS97_SP2_DIR")
    if expanded:
        root = Path(expanded)
        if root.name.lower() != "vssp2":
            candidates = [p for p in root.rglob("*")
                          if p.is_dir() and p.name.lower() == "vssp2"]
            if len(candidates) != 1:
                raise SystemExit("VS97_SP2_DIR must be VSSP2 or contain one VSSP2 tree")
            root = candidates[0]
        return root, None

    iso = Path(os.environ["VS97_SP2_ISO"])
    identity = SOURCE_IDENTITIES["vc5-sp2"]
    if str(iso.stat().st_size) != identity["size"] or sha256(iso) != identity["sha256"]:
        raise SystemExit("VS97_SP2_ISO does not match the pinned Archive.org image")
    extracted = work / "sp2-iso"
    log("Extracting the pinned Microsoft SP2 carrier ISO ...")
    helpers.extract_7z(iso, extracted, iso=True)
    candidates = [p for p in extracted.rglob("*")
                  if p.is_dir() and p.name.lower() == "vssp2"]
    if len(candidates) != 1:
        raise SystemExit(f"expected one VSSP2 tree in {iso}, found {len(candidates)}")
    return candidates[0], iso


def stage_base_extras(work: Path, stage_msvc: Path) -> None:
    vc_bin = helpers.find_vc_bin(work / "vc5-iso")
    if vc_bin is None:
        raise SystemExit("cannot relocate the staged VC5 RTM source tree")
    vc = vc_bin.parent
    rows: list[dict[str, str]] = []
    mappings = (
        ("CRT/SRC", "crt-src"),
        ("ATL/INCLUDE", "include"),
        ("ATL/SRC", "atl-src"),
        ("REDIST", "redist"),
        ("DEBUG", "debug"),
    )
    for source, destination in mappings:
        try:
            src = require_dir(vc, source)
        except SystemExit:
            continue
        overlay_tree(src, stage_msvc / destination, f"vc5-rtm/{source}", rows)


def apply_sp2(sp2: Path, stage_msvc: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    mappings = (
        ("ENU/VC/BIN", "bin"),
        ("ALL/SHARED/BIN", "bin"),
        ("ALL/VC/INCLUDE", "include"),
        ("ALL/VC/ATL/INCLUDE", "include"),
        ("ALL/VC/LIB", "lib"),
        ("ALL/VC/MFC/LIB", "lib"),
        ("ALL/VC/MFC/SRC", "mfc-src"),
        ("ALL/VC/CRT/SRC", "crt-src"),
        ("ALL/VC/REDIST", "redist"),
        ("ALL/VC/DEBUG", "debug"),
    )
    for source, destination in mappings:
        src = require_dir(sp2, source)
        before = len(rows)
        overlay_tree(src, stage_msvc / destination, f"VSSP2/{source}", rows)
        log(f"SP2 overlay {source} -> msvc/{destination}: {len(rows) - before} files")
    return rows


def verify(stage_msvc: Path) -> None:
    bin_dir = stage_msvc / "bin"
    for name, expected_hash in SP2_TOOL_SHA256.items():
        path = find_ci(bin_dir, name, directory=False)
        if path is None:
            raise SystemExit(f"SP2 verification: msvc/bin/{name} is missing")
        actual_hash = sha256(path)
        actual_version = fixed_file_version(path)
        if actual_hash != expected_hash:
            raise SystemExit(f"SP2 verification: {name} hash is {actual_hash}")
        if actual_version != SP2_TOOL_VERSIONS[name]:
            raise SystemExit(f"SP2 verification: {name} version is {actual_version}")
        log(f"verified {name}: {actual_version} {actual_hash[:12]}")

    for name in ("cl.exe", "cvtres.exe", "rc.exe", "rcdll.dll"):
        if find_ci(bin_dir, name, directory=False) is None:
            raise SystemExit(f"RTM companion required by SP2 is missing: {name}")
    for name in ("libc.lib", "libcmt.lib", "msvcrt.lib", "nafxcw.lib"):
        if find_ci(stage_msvc / "lib", name, directory=False) is None:
            raise SystemExit(f"SP2 archive required for the census is missing: {name}")


def write_provenance(stage: Path, overlay_rows: list[dict[str, str]],
                     vc5_iso: Path, sp2_iso: Path | None) -> None:
    provenance = stage / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    with (provenance / "sources.tsv").open("w", newline="") as stream:
        fields = ("source", "url", "size", "md5", "sha1", "sha256")
        writer = csv.DictWriter(stream, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for source in ("vc5-rtm", "vc5-sp2"):
            writer.writerow({"source": source, **SOURCE_IDENTITIES[source]})
    with (provenance / "sp2-overlay.tsv").open("w", newline="") as stream:
        fields = ("destination", "source", "size", "sha256")
        writer = csv.DictWriter(stream, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(overlay_rows)

    manifest = []
    for root in (stage / "msvc", stage / "dx", stage / "ninja"):
        if root.is_dir():
            manifest.extend(p for p in root.rglob("*") if p.is_file())
    with (provenance / "files.sha256").open("w") as stream:
        for path in sorted(manifest, key=lambda p: str(p.relative_to(stage)).lower()):
            stream.write(f"{sha256(path)}  {path.relative_to(stage).as_posix()}\n")

    (provenance / "toolchain.toml").write_text(
        'compiler = "Microsoft Visual C++ 5.0"\n'
        'service_level = "SP2"\n'
        'language = "ENU"\n'
        'linker_file_version = "5.2.0.7132"\n'
        'directx_sdk = "5.0"\n'
        'base = "Visual Studio 97 Professional Disc 3"\n'
        'overlay = "VSSP2/ENU + VSSP2/ALL"\n'
    )


def package(stage: Path, output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "tar", "--sort=name", "--format=gnu", "--owner=0", "--group=0",
        "--numeric-owner", f"--mtime=@{RELEASE_EPOCH}",
        "--transform", f"s|^\\.|{RELEASE_ROOT}|", "-C", str(stage),
        "-cJf", str(output), ".",
    ], check=True)
    return sha256(output)


def main() -> None:
    vc5_iso = Path(os.environ["VC5_ISO"])
    identity = SOURCE_IDENTITIES["vc5-rtm"]
    if str(vc5_iso.stat().st_size) != identity["size"] or sha256(vc5_iso) != identity["sha256"]:
        raise SystemExit("VC5_ISO does not match the pinned Archive.org Disc 3 image")

    output = Path(os.environ.get(
        "OUTPUT", str(REPO / "build" / "rom1-toolchain-vc50-sp2-dx5-r1.tar.xz")))
    requested_work = os.environ.get("WORK_DIR")
    if requested_work:
        work = Path(requested_work).resolve()
        if work.exists() and any(work.iterdir()):
            raise SystemExit(f"WORK_DIR must be absent or empty: {work}")
        work.mkdir(parents=True, exist_ok=True)
    else:
        work = Path(tempfile.mkdtemp(prefix="rom1-sp2-release-"))
    stage = work / "stage"
    stage.mkdir(parents=True)
    log(f"work: {work}")
    log(f"output: {output}")

    try:
        stage_msvc = helpers.step1_vc5_base(work, stage)
        stage_base_extras(work, stage_msvc)
        sp2, sp2_iso = locate_sp2(work)
        overlay_rows = apply_sp2(sp2, stage_msvc)
        helpers.bundle_msdis(work, stage_msvc)
        helpers.bundle_rc(work, stage_msvc)
        verify(stage_msvc)
        helpers.step3_dxsdk(work, stage)
        ninja_exe = os.environ.get("NINJA_WIN_EXE")
        if ninja_exe:
            (stage / "ninja").mkdir(parents=True, exist_ok=True)
            shutil.copy2(ninja_exe, stage / "ninja" / "ninja.exe")
        else:
            helpers.step4_ninja(work, stage)
        if not (stage / "ninja" / "ninja.exe").is_file():
            raise SystemExit("ninja.exe is missing")
        write_provenance(stage, overlay_rows, vc5_iso, sp2_iso)
        digest = package(stage, output)
        log(f"created {output} ({output.stat().st_size} bytes)")
        log(f"sha256 {digest}")
    finally:
        if not os.environ.get("KEEP_WORK"):
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
