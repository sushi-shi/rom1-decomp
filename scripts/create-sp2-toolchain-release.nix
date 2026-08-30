# Rebuild the exact RoM1 VC5 SP2 + DirectX 5 toolchain release from preserved
# Microsoft media. The expanded SP2 tree lives on VC_TECH_PRE.ISO even though
# the disc's catalog title describes its unrelated top-level preview content.
{ pkgs ? import <nixpkgs> {} }:

let
  vc5-iso = pkgs.fetchurl {
    name = "vs97-pro-disc3-vc5.iso";
    url = "https://archive.org/download/microsoft-visual-studio-97-professional-edition-disc-3/Microsoft%20Visual%20Studio%2097%20Professional%20Edition%20-%20Disc%203.iso";
    hash = "sha256-mRAfsB9WS6nMUMvL+GLDNM0b4WoujCd8uB+aUAy2QT8=";
  };

  sp2-iso = pkgs.fetchurl {
    name = "vc-tech-pre-vssp2.iso";
    url = "https://archive.org/download/vc-tech-pre/VC_TECH_PRE.ISO";
    hash = "sha256-2oSM9pArlGHBFQM3Cibya8MN+LVEqNFOju60EQM5/XU=";
  };

  dxsdk-archive = pkgs.fetchurl {
    name = "idx5sdk.exe";
    url = "https://archive.org/download/idx5sdk/idx5sdk.exe";
    hash = "sha256-bN6bpxiGbiHosZe1mfyRk6kES4FZr4ut2+/sFq5TG1E=";
  };

  ninja-zip = pkgs.fetchurl {
    name = "ninja-win.zip";
    url = "https://github.com/ninja-build/ninja/releases/download/v1.12.1/ninja-win.zip";
    hash = "sha256-9VD+xwW21v9Y8ts8N0wid6N2kWeNarpGOty7EpEIRno=";
  };
in pkgs.mkShell {
  packages = [ pkgs.p7zip pkgs.gnutar pkgs.xz pkgs.python3 ];
  shellHook = ''
    export VC5_ISO="${vc5-iso}"
    export VS97_SP2_ISO="${sp2-iso}"
    export DXSDK_EXE="${dxsdk-archive}"
    export NINJA_WIN_ZIP="${ninja-zip}"
    export ROM1_DIR="$PWD"
    exec python3 ${./create-sp2-toolchain-release.py}
  '';
}
