# RoM1 VC5 SP3 + DirectX 5 analysis bootstrap r1

This tooling asset supports executable analysis, archive census development,
Wine-prefix setup, and future compiler comparison. It contains:

- the reproducible VC5 SP3 payload inherited from Gruntz tooling;
- exact DirectX 5 SDK `cdrom/sdk/inc` and `cdrom/sdk/lib` contents from
  `idx5sdk.exe` (`sha256 6cde9ba718866e21e8b197b599fc9193a9044b8159af8baddbefec16ae531b51`);
- static release CRT/MFC archives (`LIBCMT.LIB`, `NAFXCW.LIB`);
- the era resource/PDB/linker dependencies and Windows Ninja driver.

Asset:

```text
rom1-bootstrap-vc50-sp3-dx5-r1.tar.xz
size     16,974,956 bytes
sha256   ca82aaafbef4cde8f0fa345311410c710934cf94c72d5cce1a1f371860596fd0
```

Important: this is not the RoM1 matching compiler. Retail `ALLODS.EXE` has a
5.02 PE linker stamp, which rejects SP3's 5.10.7303 linker and leaves VC5 SP1
and SP2 as the live candidates. The repository prevents compile/link use until
both candidates are compared and one exact payload is selected.
