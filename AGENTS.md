## Objective and authority

- Reconstruct Rage of Mages 1 so the selected original VC5 servicing payload
  emits COFF and, eventually, a linked image matching retail `ALLODS.EXE`.
- Retail bytes, ordered recovered relocations, exact FPO records, import/debug
  directories, and reviewed configuration are authority. Inventory heuristics,
  generated PDBs, delinked objects, inferred names, and cross-project patterns
  are working evidence, never new ground truth.
- Correct source structure outranks a transient fuzzy score. Do not distort
  types, ownership, storage, control flow, calling conventions, or referents.

## Exact environment discipline

- Work in the pinned `nix develop` environment.
- The bundled VC5 SP3 payload is a bootstrap inherited from Gruntz. Retail's
  linker stamp is 5.02 and rejects SP3. Never compile or promote static-library
  labels with it as though it were the matching compiler.
- `rom1 tool compiler-census` must compare the complete SP1/SP2 matrix and
  write an exact, hashed selection before `cl` or `link` may run.
- DirectX 5 is exact. Do not upgrade SDK headers or import libraries.
- Smacker declarations are exact for the complete retail-used ABI only. Do not
  call unimported 3.1L declarations recovered merely because the 3.2f header is
  close.

## Evidence discipline

- Treat all 4,384 FPO records as an exact subset of the function partition,
  including their extents, locals, parameters, prolog, saved-register, BP,
  SEH, and frame fields. Refine only with stronger executable evidence and
  preserve the original record.
- `config/retail/functions.tsv` is generated only for its first bootstrap and
  is manually maintained thereafter, exactly as in Gruntz. `retail-census`
  must never rewrite it; `retail-partition` validates required FPO/EH/XC/thunk
  starts and kinds, and rewrites the file only with the explicit one-time
  `--bootstrap-functions --write` pair.
- `config/retail/relocs.tsv` is the single relocation authority because retail
  is `/FIXED` and has no `.reloc`. Regenerate it only with the pinned local
  Vostok recovery script and review any diff.
- Strings, imports, sections, debug records, and PE facts are address-bearing
  evidence. Keep their RVAs/file offsets and regenerate with
  `rom1 tool retail-census`; do not paste hand-normalized substitutes.
- A static-library function is promoted only after a unique exact extent and
  union-relocation-masked match under the selected compiler archive set.
  Collisions remain explicit.
- Inspect ownership, callers/callees, strings, types, and retail disassembly
  before editing. Compare the first real divergence and ordered relocations
  after each build.

## Gruntz parity

- Infrastructure comes from `sushi-shi/gruntz-decomp` commit
  `00960e4a9beb6dfbf3f7e604bd5050ef8bf5e078`.
- Preserve CLI, graph, generated-path, verification, and matching behavior.
  Any target seam must be recorded in `config/gruntz_parity.tsv` with hashes
  and a reason.
- Never import Gruntz addresses, compiler conclusions, ILT assumptions,
  library membership, reconstructed game source, or evidence rows into RoM1.

## Handoff

- Verify retail census, relocations, vendor ABI, parity, Python tests, Vostok
  tests, and Nix evaluation before handoff.
- A build is not authoritative while compiler selection remains unresolved;
  report that gate plainly instead of generating SP3 match artifacts.
