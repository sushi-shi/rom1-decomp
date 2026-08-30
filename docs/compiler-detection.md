# Exact VC5 servicing detection

RoM1's PE Optional Header reports linker version `5.02`. The executable has no
Rich header, so no Rich-product record can identify `cvtres` or the compiler.

Microsoft KB170367 maps the VC5 linkers as follows:

| Servicing level | `link.exe` |
| --- | --- |
| RTM | 5.00.7022 |
| SP1 | 5.02.7132 |
| SP2 | 5.02.7132 |
| SP3 | 5.10.7303 |

The PE stamp hard-rejects RTM and SP3. It does not distinguish SP1 from SP2.
The complete official SP2 payload is available, so the tracked policy tests it
first and acquires SP1 only if SP2 fails. Chronology and file dates are not
substitutes for the executable/archive panel.

`rom1 tool compiler-census` implements the finite decision:

1. hash and version every compiler/linker role and candidate archive;
2. reject candidates incompatible with the PE linker stamp;
3. compare every one of the 4,384 exact FPO extents against every relevant
   archive member, masking the union of retail and COFF relocation operands;
4. preserve every collision rather than turning it into a provider claim;
5. select SP2 only if its complete tool panel, actual linker version, and a
   non-empty bijective exact archive witness set all pass;
6. acquire and test SP1 only if that SP2-first panel fails.

SP2 passes. `LINK.EXE` is 5.2.0.7132; the FPO panel has 1,010 bijective and
1,170 ambiguous matches. The full 12,563-start FID has 1,354 HIGH providers
(861 `NAFXCW`, 421 `LIBCMT`, 72 `LIBCIMT`) and no off-start candidates. Those
HIGH rows are promoted to `functions_static_libs.tsv`. The active tools and
archives are checked against their aggregate hashes before compile, link, or
provider promotion.

The rejected SP3 control has 1,001 bijective plus the same 1,170 ambiguous FPO
matches. Its nine-witness deficit is useful corroboration, but its incompatible
5.10 linker is already decisive.

Sources: [Microsoft KB170367](https://ftp.zx.net.nz/pub/mirror/ftp.microsoft.com/MISC/KB/en-us/170/367.HTM)
and [Microsoft SP2 notes](https://ftp.zx.net.nz/pub/mirror/ftp.microsoft.com/MISC/KB/en-us/172/610.HTM).
