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
Chronology, file dates, another game's compiler, and a close aggregate score
are not sufficient.

`rom1 tool compiler-census` implements the finite decision:

1. hash and version every compiler/linker role and candidate archive;
2. reject candidates incompatible with the PE linker stamp;
3. compare every one of the 4,384 exact FPO extents against every relevant
   archive member, masking the union of retail and COFF relocation operands;
4. preserve collisions and calculate candidate-exclusive exact witnesses;
5. select only when every surviving payload is present and one candidate has a
   unique decisive witness panel.

The Gruntz SP3 bootstrap remains useful for parser and archive calibration. Its
conservative FPO scan has 1,001 bijective and 1,170 ambiguous matches. The
companion Gruntz-style masked FID over all 12,563 manual starts has 1,336 HIGH
providers (851 `NAFXCW`, 413 `LIBCMT`, 72 `LIBCIMT`) and currently no off-start
residuals. Both reports are tracked under `config/evidence/`, but SP3's rejected
linker means none may enter `functions_static_libs.tsv`. `fid-census --write`
uses the same exact-toolchain gate and therefore fails closed while selection
is unresolved.

Sources: [Microsoft KB170367](https://ftp.zx.net.nz/pub/mirror/ftp.microsoft.com/MISC/KB/en-us/170/367.HTM)
and [Microsoft SP2 notes](https://ftp.zx.net.nz/pub/mirror/ftp.microsoft.com/MISC/KB/en-us/172/610.HTM).
