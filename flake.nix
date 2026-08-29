{
  description = "Rage of Mages 1 (1998, Monolith / WAP32) binary-matching environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/64c08a7ca051951c8eae34e3e3cb1e202fe36786";

    rust-overlay = {
      url = "github:oxalica/rust-overlay/6cddd512fa2bf7231f098d3a2f92f6e4cff71e0a";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    vostok-delinker-src = {
      # The reviewed-data-topology branch (the one homm2-decomp pins): a SUPERSET of
      # the old PR#11 pin (fix/absolute-data-relocs - DIR32 for absolute data/code
      # refs, REL32 for branches), plus the data/section/contribution/reloc-alias
      # manifests the DATA-match loop needs, and it retains REAL PDB identities for
      # byte-identical function groups instead of coalescing them to synthetic names
      # (the legacy behaviour is now opt-in behind --coalesce-common-functions).
      # Measured on our own tree, same base objs: exact 2366 -> 2385 (+19).
      # Needs .idata IAT symbols in the synth PDB (synth_pdb.py emits all 456) or it
      # hard-errors on the first IAT relocation target.
      url = "github:srp-survarium/vostok-delinker/81d34b204a0384a92cf3b4c641a8430256b2922e";
      flake = false;
    };

    objdiff-src = {
      # Same release we used to download prebuilt; `objdiff-cli` is now built from
      # it so the BSS-extent patch below can apply. The GUI stays prebuilt.
      url = "github:encounter/objdiff/v3.7.3";
      flake = false;
    };
  };

  outputs = { self, nixpkgs, rust-overlay, vostok-delinker-src, objdiff-src }:
    let
      system = "x86_64-linux";

      pkgs = import nixpkgs {
        inherit system;
        overlays = [ rust-overlay.overlays.default ];
        config.allowUnfree = true;
      };

      # Nightly: the delinker uses `#![feature(os_string_truncate)]`.
      rust = pkgs.rust-bin.nightly.latest.default.override {
        extensions = [ "rust-src" "rustfmt" "clippy" ];
      };
      nightly-rustPlatform = pkgs.makeRustPlatform { cargo = rust; rustc = rust; };

      # vostok-delinker - splits the EXE into per-symbol COFF "target" objects for objdiff.
      vostok-delinker = nightly-rustPlatform.buildRustPackage {
        pname = "vostok-delinker";
        version = "0.1.0";
        src = vostok-delinker-src;
        cargoHash = "sha256-ry3TH1fz7Aj/JdbmlgQFFn29m8E7EQHyGaVXnZTEcXo=";
        # UPSTREAM-PENDING. --data-manifest rejected one rva claimed by two objects,
        # but a COMDAT is emitted into EVERY object that uses it and folded by the
        # linker onto one rva, so all owners are correct. The section manifest already
        # permits exactly this (`compatible_folded_comdat_alias`); the data manifest
        # never got the same treatment. Mirrors it there. docs/data-attribution.md §3b.
        # ILT: link.exe /INCREMENTAL routes function-ADDRESS references (vtable
        # slots, fn-ptr tables) through a 5-byte `jmp rel32` thunk band at the
        # start of .text. The thunk is a link-time artifact - cl cannot name a
        # symbol that does not exist until link, so the original object's DIR32
        # named the BODY. Resolve through the thunk to reconstruct that, the same
        # way an IAT slot is resolved back to its import. docs/patterns/ilt-thunk-
        # indirection.md.
        # COMDAT leader: `finish_data_comdats` demanded an external definition at
        # section offset 0, which is not what COFF means and not what cl emits.
        # Under /GR a class vtable COMDAT holds the `??_R4` complete-object-locator
        # POINTER (an unnamed word) at offset 0 and `??_7<class>@@6B@` at offset 4,
        # and the vtable symbol is that COMDAT's leader. Take the lowest-offset
        # external definition instead. docs/data-attribution.md §3b-ii.
        # Grouped section names: the section manifest's storage check demanded an
        # exact `.rdata` / `.data` / `.bss`, with one hand-rolled exception for
        # `.CRT$`. A `$` suffix is COFF's grouped-section form (a linker ordering
        # key, stripped at link time), and cl emits every RTTI record that way -
        # `??_R1`..`??_R4` in `.rdata$r`. Compare the group prefix instead.
        # Legacy data into a COMDAT: `with_sections` adopted the FIRST manifest
        # section of each storage as the container for definitions the manifest
        # does not place, and with the candidate section manifest that is a
        # per-symbol COMDAT. A COMDAT holds exactly cl's one symbol, so the
        # appended definition (plus its alignment gap) is content the base object
        # does not have. Only an ordinary section may be the fallback.
        # Data hypothesis must CONTAIN the rva: `hypothesis_owner_and_addend_for_rva`
        # ranks enrolled definitions by `(!contains, distance, ...)` but returns the
        # best one even when NOTHING contains the rva, with an addend that is
        # unbounded in both directions - and both callers consult it BEFORE the
        # `--recover-data-relocs-from-pdb` fallback, so that guess beats an
        # exact-address PDB symbol. Measured: 1,020 of 21,730 enrolled-symbol data
        # relocations decomposed past their symbol's end, over 185 objects -
        # `??_R4CGruntVoice@@6B@ + 0x10800` into a 0x14 B RTTI locator (750 sites:
        # every /GX registration stub's `mov eax,<FuncInfo>`), `_inflate_mask +
        # 0x3db4` into 0x44 B (164), and negative addends where the nearest enrolled
        # datum sits AFTER the target. Not enrolling an rva is what the PDB fallback
        # is for. docs/build-system.md § "The EH funclet band".
        # Canonical alias owners: a reviewed reloc-alias manifest is checked in,
        # and no checked-in file may carry a volatile CodeView `$S<n>` ordinal
        # (it renumbers on any TU churn). A trailing bare `$S` marks the owner
        # as CANONICAL: match the live symbol by its ordinal-stripped spelling
        # and emit the live name. Negative addends need no change - the manifest
        # already takes two's-complement hex (`0xffffffff` = the array-1 loop
        # idiom containment can never name).
        # Unprovisioned-identity refusal: every data identity the delinker emits
        # is PROVIDED, never invented. pdb_synth seeds a fence at each reloc
        # target no real name reaches - `DAT_<va>` when only library link-bands
        # reference it (deliberately synthetic, emitted as-is), `UNPROVISIONED_
        # <va>` when any game band does. The PDB-fallback paths refuse to emit
        # an `UNPROVISIONED_` referent (bail names the rva + the remedy), and
        # the writable-statics fallback's no-symbol case bails the same way
        # instead of silently DROPPING the relocation from the emitted object.
        patches = [
          ./nix/patches/vostok-data-manifest-folded-comdat.patch
          ./nix/patches/vostok-ilt-thunk-resolution.patch
          ./nix/patches/vostok-comdat-leader-nonzero-offset.patch
          ./nix/patches/vostok-grouped-section-names.patch
          ./nix/patches/vostok-legacy-data-not-into-comdat.patch
          ./nix/patches/vostok-data-hypothesis-must-contain.patch
          ./nix/patches/vostok-canonical-alias-owner.patch
          ./nix/patches/vostok-unprovisioned-identity-refusal.patch
          # RoM1 retail strips `.reloc`; consume the reviewed site manifest
          # generated by the pinned local recovery script.
          ./nix/patches/vostok-reloc-manifest.patch
        ];
      };

      # objdiff - upstream prebuilt Linux binaries (not in nixpkgs), so foreign ELF
      # patched by autoPatchelfHook. Supports x86 + COFF, our MSVC target.
      objdiffVersion = "3.7.3";
      objdiffUrl = name:
        "https://github.com/encounter/objdiff/releases/download/v${objdiffVersion}/${name}";
      objdiffGuiLibs = with pkgs; [
        libGL libxkbcommon wayland fontconfig freetype
        libx11 libxcursor libxi libxrandr libxcb
      ];

      # objdiff-cli is built FROM SOURCE (the GUI below stays a prebuilt download)
      # so that the two scoring patches below can apply.
      #
      # UPSTREAM-PENDING objdiff-bss-inferred-extent: `.bss` has no bytes, so a BSS
      # symbol's size is objdiff's whole comparison - but COFF encodes a symbol size
      # only for a COMMON symbol, so `infer_symbol_sizes` synthesises one from the
      # distance to the next symbol: the object PLUS its allocator's padding. Our two
      # sides use different allocators (cl for the base, the delinker's aligned append
      # for the target), so that span differs for reasons that are not the program.
      # Census over the whole tree: 364 paired `.bss` symbols, 51 disagreements, every
      # single delta 3/4/6 bytes - all sub-alignment padding, none a real size. The
      # extent audit that DOES bite lives in `rom1.build.data_manifest` (a reviewed
      # extent must fit the span to its retail neighbour, or both rows are withheld).
      # Upstream cannot relax this globally: for a format that DOES state sizes the
      # comparison is real. Drop the patch if objdiff stops comparing INFERRED sizes.
      # docs/patterns/bss-symbol-size-inference-hole.md.
      #
      # UPSTREAM-PENDING objdiff-score-reloc-addend: x86 COFF `DIR32` has no addend
      # field - the addend sits in the instruction's displacement, which is exactly
      # the operand the diff masks as "relocated". objdiff recovers it, and the `all`
      # / `name_address` reloc modes do compare it, but `data_value` (what we use)
      # short-circuits that clause and drops the addend along with the name. So
      # `g_clut + 0x20000` vs `g_clut + 0x1fffe` scored IDENTICAL - the one operand
      # class where a wrong constant is free, and it hid a live off-by-one across a
      # 3 x 32768-entry LUT (commit 61d15c531). The patch compares the addend when
      # both sides resolve to the SAME symbol and the reloc type's addend is a plain
      # symbol offset (a new `Arch` predicate, default false; REL32 keeps its current
      # behaviour since its stored value is site-relative). Upstream does not do it
      # because `data_value` exists for projects with unreliable target symbol names,
      # where the pointed-to VALUE is the trusted signal - nobody had noticed the
      # addend is a third signal that survives unreliable names. Drop the patch once
      # objdiff scores addends under `data_value` (or grows an addend knob).
      # docs/patterns/reloc-addend-is-masked-diff-the-addends.md.
      objdiff-cli = nightly-rustPlatform.buildRustPackage {
        pname = "objdiff-cli";
        version = objdiffVersion;
        src = objdiff-src;
        patches = [
          ./nix/patches/objdiff-bss-inferred-extent.patch
          ./nix/patches/objdiff-score-reloc-addend.patch
        ];
        cargoHash = "sha256-Z9vyUj35nrHuUoOYM54RLCn7CzcQ6k3A6FsDYKCVqVM=";
        cargoBuildFlags = [ "-p" "objdiff-cli" ];
        cargoTestFlags = [ "-p" "objdiff-core" "-p" "objdiff-cli" ];
        cargoInstallFlags = [ "-p" "objdiff-cli" ];
      };

      objdiff = pkgs.stdenv.mkDerivation {
        pname = "objdiff";
        version = objdiffVersion;
        src = pkgs.fetchurl {
          url = objdiffUrl "objdiff-linux-x86_64";
          hash = "sha256-1pzhzJUl/BJQP2XS333KIfkx1YYi8ZyRdPMv5MnJGyA=";
        };
        dontUnpack = true;
        nativeBuildInputs = [ pkgs.autoPatchelfHook pkgs.makeWrapper ];
        buildInputs = [ pkgs.stdenv.cc.cc.lib ] ++ objdiffGuiLibs;
        installPhase = ''
          install -Dm755 $src $out/bin/objdiff
          wrapProgram $out/bin/objdiff \
            --prefix LD_LIBRARY_PATH : "${pkgs.lib.makeLibraryPath objdiffGuiLibs}"
        '';
      };

      # RoM1 retail target: Russian Buka Hello__0 build, byte-identical engine
      # code to the English Interplay and Polish releases.  The executable is
      # fetched directly from the archived CD, exactly like the Gruntz target.
      rom1-exe = pkgs.fetchurl {
        name = "ALLODS.EXE";
        url = "https://archive.org/download/allods_201912/ALLODS.iso/ALLODS/ROM.EXE";
        sha256 = "sha256-W6gh83NW0toOHrkH3iiycIcU1uJgS1yu89r0KEua99M=";
      };

      # Runtime DLLs - proprietary libs the rebuilt EXE LOADS to run.

      # Smacker 3.1L runtime shipped beside ROM.EXE.
      rom1-smackw32 = pkgs.fetchurl {
        name = "SMACKW32.DLL";
        url = "https://archive.org/download/allods_201912/ALLODS.iso/ALLODS/SMACKW32.DLL";
        sha256 = "sha256-ef9A6E/TOZMK01h2itRAjmKAB0pn47FzNDTSKUsPW8U=";
      };

      # Runtime directory remains a separate derivation as in Gruntz.
      rom1-runtime = pkgs.runCommand "rom1-runtime" {
        rom1_smackw32 = rom1-smackw32;
      } ''
        mkdir -p "$out"
        cp "$rom1_smackw32" "$out/SMACKW32.DLL"
      '';

      # Bootstrap compiler candidate: Gruntz's reproducible VC5 SP3 payload.
      # `rom1 tool compiler-census` must identify the exact RoM1 servicing level
      # before library claims or the first game-function bank are final.
      #
      # Expected unpacked layout:
      # * msvc/{bin,include,lib (LIBCMT+NAFXCW static MFC)}
      # * dx/{Include,Lib} (DirectX 5 SDK)
      # * ninja/ninja.exe.
      # msvc/bin includes MSDIS100.DLL (the VC5 disassembler link.exe imports at
      # load), MSPDB50.DLL, and - since r3 - RC.EXE + RCDLL.DLL + MSVCP50.DLL (the era resource
      # compiler; the .rc -> .res step drives the real tool, no python fallback).
      # All four are bundled by scripts/create-toolchain-release.py from the VS97
      # Disc 3 ISO's DEVSTUDIO/SHAREDIDE/BIN.
      dx5sdk = pkgs.fetchurl {
        name = "idx5sdk.exe";
        url = "https://archive.org/download/idx5sdk/idx5sdk.exe";
        hash = "sha256-bN6bpxiGbiHosZe1mfyRk6kES4FZr4ut2+/sFq5TG1E=";
      };

      rom1-toolchain = pkgs.runCommand "rom1-bootstrap-vc50-sp3-dx5" {
        src = pkgs.fetchurl {
          name = "gruntz-toolchain-vc50.tar.xz";
          url = "https://github.com/sushi-shi/gruntz-decomp/releases/download/toolchain-vc50-sp3-r3/gruntz-toolchain-vc50.tar.xz";
          sha256 = "sha256-sZgl957g2+6wlrAPxIa1OcaDqlcG8PXsXVOKWc5KeZ8=";
        };
        nativeBuildInputs = [ pkgs.gnutar pkgs.xz pkgs.p7zip pkgs.findutils ];
      } ''
        mkdir -p "$out"
        tar xf "$src" -C "$out" --strip-components=1
        mkdir -p "$TMPDIR/dx5-outer" "$TMPDIR/dx5-inner"
        7z x -y "${dx5sdk}" -o"$TMPDIR/dx5-outer" >/dev/null
        dx5_inner="$(find "$TMPDIR/dx5-outer" -type f -iname DX5SDK.EXE -print -quit)"
        test -n "$dx5_inner"
        7z x -y "$dx5_inner" -o"$TMPDIR/dx5-inner" >/dev/null
        dx5_inc="$(find "$TMPDIR/dx5-inner" -type d -ipath '*/sdk/inc' -print -quit)"
        dx5_lib="$(find "$TMPDIR/dx5-inner" -type d -ipath '*/sdk/lib' -print -quit)"
        test -n "$dx5_inc" -a -n "$dx5_lib"
        rm -rf "$out/dx"
        mkdir -p "$out/dx"
        cp -R "$dx5_inc" "$out/dx/Include"
        cp -R "$dx5_lib" "$out/dx/Lib"
      '';

      rom1-toolchain-release = pkgs.runCommand
        "rom1-bootstrap-vc50-sp3-dx5-r1.tar.xz" {
          nativeBuildInputs = [ pkgs.gnutar pkgs.xz ];
        } ''
          mkdir -p "$TMPDIR/release/rom1-bootstrap-vc50-sp3-dx5"
          cp -R ${rom1-toolchain}/. "$TMPDIR/release/rom1-bootstrap-vc50-sp3-dx5/"
          tar --sort=name --mtime=@925473600 --owner=0 --group=0 --numeric-owner \
            -C "$TMPDIR/release" -cJf "$out" rom1-bootstrap-vc50-sp3-dx5
        '';

      # `rom1` as a real PATH executable so the CLI works in ANY shell (bash, fish,
      # zsh) - a shellHook function would not survive `nix develop --command fish`.
      # The CLI is `python -m rom1` (rom1.__main__ -> rom1.cli.main); scripts/
      # is THE package root, put on PYTHONPATH so the package + every `python -m
      # rom1.<x>` child import resolves.
      rom1-cli = pkgs.writeShellScriptBin "rom1" ''
        # Resolve the repo/worktree root robustly: ROM1_DIR (set by the shell
        # hook), else walk up from $PWD to the dir holding scripts/rom1/cli.py
        # (so `rom1` works from build/, src/, any subdir), else git toplevel.
        d="''${ROM1_DIR:-}"
        if [ -z "$d" ]; then
          p="$PWD"
          while [ "$p" != "/" ]; do
            if [ -f "$p/scripts/rom1/cli.py" ]; then d="$p"; break; fi
            p="$(dirname "$p")"
          done
        fi
        [ -n "$d" ] || d="$(git rev-parse --show-toplevel 2>/dev/null || true)"
        if [ ! -f "$d/scripts/rom1/cli.py" ]; then
          echo "rom1: repo root not found (run inside the rom1 checkout, or set ROM1_DIR)" >&2
          exit 2
        fi
        export ROM1_DIR="$d"
        export PYTHONPATH="$d/scripts''${PYTHONPATH:+:$PYTHONPATH}"
        exec python3 -m rom1 "$@"
      '';

      # Wrap nvim to auto-load the in-repo editor/nvim plugin (:Rom1), leaving the
      # user's own config intact. A wrapper SCRIPT on PATH (not a shell function)
      # survives `nix develop --command fish`, like rom1-cli; the real nvim is
      # resolved before we shadow it, ROM1_NVIM_WRAPPED guards nested shells, and
      # the banner announces the change.
      nvimShimHook = ''
        if [ -z "''${ROM1_NVIM_WRAPPED:-}" ] && command -v nvim >/dev/null 2>&1 && [ -d "$ROM1_DIR/editor/nvim" ]; then
          _gnv_real="$(command -v nvim)"
          _gnv_bin="$ROM1_DIR/build/nvim-shim"
          mkdir -p "$_gnv_bin"
          printf '#!/bin/sh\nexec "%s" --cmd "set rtp^=%s/editor/nvim" "$@"\n' "$_gnv_real" "$ROM1_DIR" > "$_gnv_bin/nvim"
          chmod +x "$_gnv_bin/nvim"
          export PATH="$_gnv_bin:$PATH"
          export ROM1_NVIM_WRAPPED=1
          echo "[rom1] nvim       : WRAPPED -> nvim now auto-loads editor/nvim (:Rom1, vt/vb/vd/vs/vx/vi/vg/V). Plain nvim is unchanged outside this shell." >&2
        fi
      '';

      # Tools common to both shells (analysis + diffing).
      commonTools = [
        rom1-cli
        rust
        objdiff
        objdiff-cli
        vostok-delinker
      ] ++ (with pkgs; [
        (python3.withPackages (ps: [ ps.pyghidra ps.libclang ]))   # pyghidra (Ghidra scripting) + libclang (clang.cindex: the permuter's precedence-correct AST mutations)
        ghidra
        ninja

        llvm            # llvm-pdbutil
        # clang-unwrapped provides the clang DRIVER (ghidra_metadata_generate/gen_labels, via
        # $ROM1_CLANG) AND clangd / clang-format / clang-tidy. It MUST be the
        # UNWRAPPED build: the nix cc-wrapper injects host (x86_64-linux) gcc/glibc
        # include paths that shadow our /imsvc MSVC headers under
        # --target=i686-pc-windows-msvc. Verified two ways:
        #   - wrapped clang  -> ghidra_metadata_generate emits 0 structs;
        #   - wrapped clangd -> <string.h> resolves to glibc -> gnu/stubs-32.h
        #     (32-bit multilib stub) "file not found".
        # So we deliberately do NOT pull in `clang-tools` (whose clangd is the
        # wrapped one with exactly that bug); clang-unwrapped supplies clangd +
        # clang-format + clang-tidy directly, and ghidra_metadata_generate reaches its driver
        # via $ROM1_CLANG.
        llvmPackages.clang-unwrapped

        ripgrep
        file
        xxd
        jq
        timidity        # synthesize exported XMI/MIDI previews to WAV
        gdb             # dynamic this/ecx tracing of the game under wine (winedbg --gdb)
      ]);

      # ONE shell for everything. `nix develop` (default) == `nix develop .#build`:
      # analysis + target-side delink + objdiff AND the MSVC 5.0/wine recompile
      # side. `.#build` is kept as an alias so every existing script/brief spelling
      # (`nix develop .#build --command ...`) keeps working. Carries all analysis
      # tools + wine + jdk21 and exports the full MSVC/wine/Ghidra env.
      rom1Shell = pkgs.mkShell {
        name = "rom1-decomp";
        packages = commonTools ++ [ pkgs.wineWow64Packages.staging pkgs.jdk21 ];
        shellHook = ''
          # Repo/worktree root, not $PWD — `nix develop` may be entered from a
          # subdir (it walks up to find flake.nix; so must we). git toplevel is
          # worktree-aware, which is exactly right for the worker pool.
          export ROM1_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
          export ROM1_EXE="${rom1-exe}"
          export ROM1_CLANG="${pkgs.llvmPackages.clang-unwrapped}/bin/clang"
          export LIBCLANG_PATH="${pkgs.llvmPackages.libclang.lib}/lib"   # clang.cindex finds libclang.so (permuter AST)
          # scripts/ is THE package root: on PYTHONPATH so `python -m rom1` and
          # every `python -m rom1.<x>` (cli/match/analysis tools) import it.
          export PYTHONPATH="$ROM1_DIR/scripts''${PYTHONPATH:+:$PYTHONPATH}"

          # Enable the repo-tracked pre-commit auto-format hook (idempotent).
          if [ "$(git -C "$ROM1_DIR" config --local core.hooksPath 2>/dev/null)" != ".githooks" ]; then
            git -C "$ROM1_DIR" config --local core.hooksPath .githooks 2>/dev/null \
              && echo "[rom1] hooks      : pre-commit auto-format on (core.hooksPath=.githooks)" >&2
          fi

          export WINEPREFIX="$ROM1_DIR/build/wineprefix"   # generated state lives under build/
          export WINEDEBUG="fixme-all,err-kerberos"
          export WINEDLLOVERRIDES="mscoree,mshtml="
          # The per-prefix wineserver is now kept alive across builds (warm `wine
          # cl` = fast rebuilds); it is a daemon shared by every `nix develop`
          # invocation on this prefix, so `nix develop --command` (e.g. the nvim
          # build loop) reconnects to it. Reap it when YOU leave an INTERACTIVE
          # shell; `rom1 clean` reaps it before removing the prefix.
          case "$-" in *i*) trap 'wineserver -k >/dev/null 2>&1 || true' EXIT ;; esac
          export ROM1_TOOLCHAIN="${rom1-toolchain}"
          export MSVC_DIR="${rom1-toolchain}/msvc"
          export DXSDK_DIR="${rom1-toolchain}/dx"
          export NINJA_DIR="${rom1-toolchain}/ninja"
          # PyGhidra (replaces Jython): pyghidra.start() bootstraps the Ghidra JVM
          # via jpype so the headless apply/export scripts run as CPython3.
          export GHIDRA_INSTALL_DIR="${pkgs.ghidra}/lib/ghidra"
          export JAVA_HOME="${pkgs.jdk21}/lib/openjdk"

          # Proprietary runtime DLL used by retail video playback.
          # These run ALONGSIDE the recompiled EXE under wine - none are needed
          # to build/link it. See docs/runtime-dlls.md.
          export ROM1_RUNTIME="${rom1-runtime}"

          # Banner -> stderr so stdout stays clean for `nix develop --command`
          # piping (e.g. rom1 status ... --json | jq).
          echo "[rom1] target EXE : $ROM1_EXE" >&2
          echo "[rom1] MSVC 5.0   : SP3 bootstrap only; retail SP1/SP2 selection is unresolved" >&2
          echo "[rom1] DirectX SDK: exact DirectX 5 headers/import libraries" >&2
          echo "[rom1] tools      : vostok-delinker, objdiff(-cli), llvm-pdbutil; ghidra is optional" >&2
          echo "[rom1] clang      : $ROM1_CLANG (unwrapped; ghidra_metadata_generate/gen_labels)" >&2
          echo "[rom1] runtime    : $ROM1_RUNTIME (SMACKW32.DLL 3.1L)" >&2
          echo "[rom1] cli        : 'rom1 <cmd>' (init/build/clangd/format/status/labels/structs/ghidra-refresh/todo)" >&2
          echo "[rom1] shell      : ONE shell - 'nix develop' (== '.#build'); everything (analysis + build/init) is here" >&2
          ${nvimShimHook}
          # `rom1 init` is idempotent and Ghidra-free; run it on startup.
          # Set ROM1_SKIP_INIT=1 when even the cheap configure/toolchain check is unwanted.
          if [ -n "$ROM1_SKIP_INIT" ]; then
            echo "[rom1] init       : skipped (ROM1_SKIP_INIT set)" >&2
          else
            if [ ! -f "$ROM1_DIR/build.ninja" ]; then
              echo "[rom1] init       : first-time local setup ..." >&2
            fi
            python3 -m rom1 init \
              || echo "[rom1] init       : failed - fix + re-run 'rom1 init'" >&2
          fi
        '';
      };

      # PLAY-only shell, deliberately NOT folded into the one shell above:
      # gamescope drags a vulkan/SDL/wlroots closure that every worker entering
      # `.#build` would have to realise for something the build loop never runs.
      # Same staging wine as the build shell - build/game-wine/prefix3 was
      # created by it.
      #
      # The runner itself is GENERATED - build/game-wine/play.sh (template:
      # scripts/rom1/graph/play.py, installed by create-wine-prefix.py,
      # refreshed by `rom1 play` = build + link + install + run). play.sh
      # enters this shell by itself when gamescope is not on PATH, so `rom1
      # play` works from the build shell. The scaling contract (gamescope's
      # nested -w/-h == the prefix's 640x480 wine virtual desktop, integer-
      # scaled x3 to 1920x1440, pillarboxed, pixel-perfect) lives in the
      # template, beside the knobs.
      playShell = pkgs.mkShell {
        name = "rom1-play";
        packages = [ pkgs.gamescope pkgs.wineWow64Packages.staging ];
        shellHook = ''
          export ROM1_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
          export WINEPREFIX="$ROM1_DIR/build/game-wine/prefix3"   # the GAME prefix, not the build one
          export WINEDLLOVERRIDES="mscoree,mshtml="
          echo "[rom1] play       : gamescope + wine, WINEPREFIX=$WINEPREFIX (runner: build/game-wine/play.sh, or \`rom1 play\`)" >&2
        '';
      };

      # The original local media/inventory toolbox remains available as an
      # explicit shell; the Gruntz-shaped matching environment stays default.
      inventoryPython = pkgs.python3.withPackages (ps: with ps; [
        construct kaitaistruct pefile capstone pillow numpy lxml python-magic rich
      ]);
      inventoryShell = pkgs.mkShell {
        name = "rom1-inventory";
        packages = with pkgs; [
          unzip p7zip unar libarchive cabextract innoextract
          cdrkit libcdio bchunk ccd2iso iat mdf2iso
          file binwalk xxd hexyl
          radare2 rizin ghidra imhex binutils detect-it-easy
          kaitai-struct-compiler
          ffmpeg-full imagemagick sox mpv
          wineWow64Packages.stable winetricks dosbox-staging
          ripgrep fd tree jq sqlite xmlstarlet inventoryPython
        ];
        shellHook = ''
          echo "[rom1] inventory  : extraction, PE/RE, media, and archive toolbox" >&2
        '';
      };

    in {
      packages.${system} = {
        inherit vostok-delinker objdiff objdiff-cli rom1-exe rom1-toolchain
          rom1-toolchain-release dx5sdk
          rom1-smackw32 rom1-runtime;
        default = vostok-delinker;
      };

      devShells.${system} = {
        # ONE shell for everything (analysis + MSVC 5.0/wine recompile). `.#build`
        # is an ALIAS of the default so every `nix develop .#build ...` spelling in
        # scripts/briefs keeps working. staging wine is used for mspdbsrv (VC5 may
        # not need it but it is a harmless superset).
        default = rom1Shell;
        build = rom1Shell;
        # Playing the game, not building it - see playShell above.
        play = playShell;
        inventory = inventoryShell;
      };
    };
}
