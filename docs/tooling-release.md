# Tooling release

The reproducible tooling asset is named
`rom1-bootstrap-vc50-sp3-dx5-r1.tar.xz`. Build it with:

```sh
nix build .#rom1-toolchain-release
sha256sum result
```

It contains the Gruntz VC5 SP3 compiler/bootstrap payload, exact DirectX 5 SDK
headers and import libraries, and the Windows Ninja binary. Fixed tar metadata
and sorted entries make the asset reproducible.

Release `r1` identity:

```text
size     16,974,956 bytes
sha256   ca82aaafbef4cde8f0fa345311410c710934cf94c72d5cce1a1f371860596fd0
```

The tag and release notes must call it an **analysis bootstrap**. It is not the
RoM1 matching compiler: retail's 5.02 linker stamp rejects its SP3 linker.
Matching releases will use a different tag only after the SP1/SP2 census writes
an exact selected payload.
