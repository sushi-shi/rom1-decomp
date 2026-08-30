# Tooling release

The selected reproducible tooling asset is named
`rom1-toolchain-vc50-sp2-dx5-r2.tar.xz`. Rebuild it from source media with:

```sh
nix-shell scripts/create-sp2-toolchain-release.nix
```

The builder verifies the pinned Visual Studio 97 Professional Disc 3 and SP2
carrier ISO hashes, stages the RTM compiler, applies only `VSSP2/ENU` and
`VSSP2/ALL`, and adds exact DirectX 5 plus Windows Ninja. It includes the full
VC/MFC/ATL headers and sources, static libraries, tools, and per-file
provenance. Fixed GNU tar metadata, normalized modes, and sorted entries make
the asset reproducible across both the writable source staging tree and the
read-only Nix store; both paths produce a byte-equal archive.

The default flake consumes this RoM1 release directly, rather than rebuilding
an implicit overlay from the Gruntz release on every fresh machine. The
`rom1-toolchain-release` derivation untars and deterministically retars that
payload, so `nix build .#rom1-toolchain-release` verifies the published asset's
packaging. The original-media builder is the full source reconstruction.

Release `r2` identity:

```text
size     43,142,876 bytes
sha256   11690189a64c703000a370faece50103f90f6ef6bac6b361469f73bd3484e47e
```

The older `tooling-vc50-sp3-dx5-bootstrap-r1` release remains an **analysis
bootstrap** and rejected-linker control. It is available from the flake as
`rom1-toolchain-sp3-bootstrap`, but it cannot satisfy the selected-toolchain
gate. SP1 remains an acquisition fallback only if SP2 later fails a concrete
representative witness.
