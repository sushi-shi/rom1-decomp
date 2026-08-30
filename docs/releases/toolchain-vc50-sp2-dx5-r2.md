# VC5 SP2 + DirectX 5 toolchain r2

This is the selected, reproducible RoM1 compiler environment. It is built from
the exact Visual Studio 97 Professional Disc 3 RTM image, overlaid only with
the official English and language-neutral `VSSP2` trees, then combined with
the exact DirectX 5 SDK and Windows Ninja.

| Source medium | Size | SHA-256 |
| --- | ---: | --- |
| [Visual Studio 97 Professional Disc 3](https://archive.org/details/microsoft-visual-studio-97-professional-edition-disc-3) | 655,605,760 | `99101fb01f564ba9cc50cbcbf862c334cd1be16a2e8c277cb81f9a500cb6413f` |
| [Microsoft VC Tech Preview carrier (`VSSP2` tree)](https://archive.org/details/vc-tech-pre) | 633,636,864 | `da848cf6902b9461c11503370a26f26bc30df8b544a8d14e8eeeb4110339fd75` |

```text
rom1-toolchain-vc50-sp2-dx5-r2.tar.xz
size     43,142,876 bytes
sha256   11690189a64c703000a370faece50103f90f6ef6bac6b361469f73bd3484e47e
```

The archive contains complete VC/MFC/ATL headers, CRT/MFC/ATL source, static
libraries, compiler/linker tools, redistributables, per-file hashes, the exact
overlay ledger, and source-media identities. File and directory modes are
normalized in addition to timestamp, owner, order, and tar format; clean
source-staging and Nix-store re-packs are byte-identical.

| Required role | File version | SHA-256 |
| --- | --- | --- |
| `CL.EXE` | 11.0.0.7022 | `bf9f9c74f756fed96e13f7f9a4273495c7dde0a1fb968e3ef6d760ad6d73dfeb` |
| `C1.DLL` | 11.0.0.7113 | `7f12a4a889c5a0277f12c391ca462657dc81ef7be769faf629331bd117983d5d` |
| `C1XX.DLL` | 11.0.0.7149 | `8b66d3f14035bfa228e79d45481318457594f65ed91f87319d23932372857d8b` |
| `C2.EXE` | 11.0.0.7153 | `592c65eea2e159a8b7bf61fb20ed12fc0dfdb3c5b7179267d34634aa7a2dc6e4` |
| `LINK.EXE` | 5.2.0.7132 | `e28424d3eefcdd96ecc8c3fe38d0fad3d33077c62026f7774eda90784d0eb4d9` |
| `CVTRES.EXE` | 4.0 | `0f82167cd888105224463feef5cadebaef970c12932597919e3033d77ed3de6c` |
| `MSPDB50.DLL` | 5.0.0.7113 | `730497a2cc447ad0ea91c52ed9aa1b9d21572f4ca37ce686937946c5a98f7f8c` |

Selection evidence:

- retail PE linker stamp `5.02` equals SP2 `LINK.EXE` 5.2.0.7132;
- all seven required compiler/linker roles are present and hash-pinned;
- the exact archive panel matches 2,180 of 4,384 FPO extents, including 1,010
  bijective matches and 1,170 retained collisions;
- the full manual-start FID promotes 1,354 globally unique exact providers.

SP1 is intentionally a fallback: acquire it only if this SP2 panel or a later
representative compilation witness fails. The older SP3 package remains a
rejected-linker control, not a matching compiler.
