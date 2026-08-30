# Configuration authority

`retail/` is executable-native evidence. `evidence/` contains diagnostic
candidate results that are useful but not promoted truth. `units.toml` is the
source/build manifest, and `compiler.toml` is the hard compiler-selection gate.

Generated files under `build/` are disposable. A name, function owner, static
library provider, or relocation becomes authoritative only through a reviewed
tracked table consumed by the same gates as the Gruntz workflow.

`retail/functions.tsv`, `retail/data.tsv`, and `retail/data_vtables.tsv` are
seeded once and manually maintained thereafter, exactly like Gruntz.
`retail-partition` validates their required executable-native subsets and
regenerates the companion extent, EH/initializer, thunk, runtime-class, and
link-band evidence. `rom1 verify vtable-scan --write` is the explicit reviewed
refresh for the vtable catalog: exact executable structure is admitted, while
only unique symbol+extent matches in the pinned SP2 archives are attributed to
static libraries. Candidate FID and compiler results remain under `evidence/`;
only globally unique exact providers from the hash-selected SP2 archive set are
promoted to `functions_static_libs.tsv`.
