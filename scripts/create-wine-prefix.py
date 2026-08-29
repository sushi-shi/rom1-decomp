#!/usr/bin/env python3
"""create-wine-prefix.py - the local Rom1 GAME environment (play/test).

The sibling of create-toolchain-release.py: a one-shot provisioner, not part
of the build loop (the BUILD prefix is `rom1 tool wine --init`). It REQUIRES
the retail resources folder - the runtime set we cannot distribute - the first
time; once game/ is populated a bare run just refreshes the rest (play.sh,
registry keys):

    python3 scripts/create-wine-prefix.py [<resources-dir>] \\
                                          [--target build/game-wine]

and assembles:

    <target>/game/     Rom1.REZ, ROM1.VRZ, *.FNT, SMACKW32.DLL
                       + ROM1.retail.EXE (the control, from build/exe/);
                       `rom1 play` installs the rebuilt ALLODS.EXE here
    <target>/play.sh   the generated gamescope runner: 640x480 integer-scaled
                       (x3, pillarboxed, pixel-perfect) - the ONE launch
                       definition, template in scripts/rom1/graph/play.py;
                       `rom1 play` = build + link + install + this
    <target>/cd/GAME/  the CD check's target: GetRom1DriveLetter() wants a
                       DRIVE_CDROM drive holding <L>:\\GAME\\ALLODS.EXE
    <target>/prefix3/  a dedicated wine prefix, SEPARATE from the build prefix

Prefix doctrine, all MEASURED (2026-08-10, the hand-grown ~/rom1-wine):
  * NO `Version=win98` key - win98 mode does not bring up the WASAPI/mmdevapi
    path, so no audio driver can initialise; the game runs fine on default.
  * NO `Audio` driver pin and no cached device tree - a pin once froze a stale
    HDMI sink and killed sound; auto-probe follows the current default sink.
  * a 640x480 virtual desktop, so the game cannot switch the host video mode.
    It is the mode the game actually runs (no saved "Resolution" value ->
    RES_640X480), which lets play.sh's gamescope use the same size as its
    nested screen and scale it whole; raise it here AND in play.sh's -w/-h
    together if a larger in-game mode is ever saved.
  * D: maps to <target>/cd as a cdrom drive + the Monolith registry key.

Idempotent: existing files (saves, an already-populated game/) are never
overwritten; only missing pieces are filled in.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from rom1.graph.play import write_play_sh  # noqa: E402  (import-light module)

#: the retail runtime set the resources folder MUST provide
REQUIRED = ("Rom1.REZ", "ROM1.VRZ", "LARGE.FNT", "MEDIUM.FNT",
            "SMALL.FNT", "TINY.FNT", "SMACKW32.DLL")

#: where the flake's `.#play` shell and `rom1 play` expect the env
DEFAULT_TARGET = REPO / "build" / "game-wine"


def log(msg: str) -> None:
    print(f"[wine-prefix] {msg}")


def die(msg: str) -> None:
    print(f"[wine-prefix] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def find_ci(d: Path, name: str) -> Path | None:
    low = name.lower()
    return next((p for p in d.iterdir() if p.name.lower() == low), None) \
        if d.is_dir() else None


def _wine(prefix: Path, *args: str) -> None:
    env = dict(os.environ, WINEPREFIX=str(prefix),
               WINEDLLOVERRIDES="mscoree,mshtml=", WINEDEBUG="fixme-all")
    subprocess.run(["wine", *args], check=False, env=env,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def setup(resources: Path | None, target: Path) -> None:
    # idempotency is decided at the DESTINATION: only what game/ lacks is
    # demanded of the resources folder, so a populated env (even one whose
    # files are symlinks elsewhere) refreshes without the retail set.
    game = target / "game"
    game.mkdir(parents=True, exist_ok=True)
    needed = [name for name in REQUIRED if find_ci(game, name) is None]
    if needed:
        if resources is None:
            die(f"{game} lacks {', '.join(needed)} and no resources folder "
                "was given (copy them from a retail Rom1 install)")
        if not resources.is_dir():
            die(f"resources folder missing: {resources}")
        found = {name: find_ci(resources, name) for name in needed}
        missing = sorted(name for name, p in found.items() if p is None)
        if missing:
            die("resources folder lacks the retail runtime set: "
                + ", ".join(missing)
                + f"\n(searched {resources}; copy them from a retail Rom1 "
                  "install)")
        for src in found.values():
            shutil.copy2(src, game / src.name)
            log(f"installed {src.name}")

    # the retail control beside the rebuilt EXE (rom1 link installs that one)
    retail = Path(os.environ.get("ROM1_EXE") or REPO / "build/exe/ALLODS.EXE")
    control = game / "ROM1.retail.EXE"
    if retail.is_file() and not control.exists():
        shutil.copy2(retail, control)
        log("installed ROM1.retail.EXE (the control)")

    # the CD check needs exactly <L>:\GAME\ALLODS.EXE on a cdrom-typed drive
    cd_game = target / "cd" / "GAME"
    cd_game.mkdir(parents=True, exist_ok=True)
    if not (cd_game / "ALLODS.EXE").exists() and retail.is_file():
        shutil.copy2(retail, cd_game / "ALLODS.EXE")
        log("installed cd/GAME/ALLODS.EXE (CD-check target)")

    prefix = target / "prefix3"
    if not (prefix / "drive_c").is_dir():
        log("creating game wineprefix (default windows version - NEVER win98, "
            "it kills audio) ...")
        prefix.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, WINEPREFIX=str(prefix),
                   WINEDLLOVERRIDES="mscoree,mshtml=")
        subprocess.run(["wineboot", "-u"], check=False, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _wine(prefix, "reg", "add", r"HKCU\Software\Wine\Explorer",
              "/v", "Desktop", "/d", "Default", "/f")
        _wine(prefix, "reg", "add", r"HKCU\Software\Wine\Explorer\Desktops",
              "/v", "Default", "/d", "640x480", "/f")

    dos_d = prefix / "dosdevices" / "d:"
    if not dos_d.is_symlink():
        dos_d.parent.mkdir(parents=True, exist_ok=True)
        if dos_d.exists():
            dos_d.unlink()
        dos_d.symlink_to(target / "cd")
        log(f"mapped D: -> {target / 'cd'}")
    _wine(prefix, "reg", "add", r"HKLM\Software\Wine\Drives",
          "/v", "D:", "/d", "cdrom", "/f")
    _wine(prefix, "reg", "add",
          r"HKLM\Software\Monolith Productions\Rom1\1.0",
          "/v", "CdRom Drive", "/d", "D:\\", "/f")
    subprocess.run(["wineserver", "-w"], check=False,
                   env=dict(os.environ, WINEPREFIX=str(prefix)))

    # the scaler: play.sh launches through gamescope with the proportional
    # (integer, pixel-perfect) upscale of the 640x480 desktop above
    write_play_sh(target, REPO)
    log("installed play.sh (gamescope integer-scaling runner)")
    log(f"ready: {target} (run {target / 'play.sh'}, or `rom1 play`)")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("resources", nargs="?",
                    help="retail resources folder (Rom1.REZ, ROM1.VRZ, "
                         "fonts, DLLs); optional once game/ is populated")
    ap.add_argument("--target", default=str(DEFAULT_TARGET),
                    help=f"environment root (default {DEFAULT_TARGET})")
    a = ap.parse_args()
    setup(Path(a.resources) if a.resources else None, Path(a.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
