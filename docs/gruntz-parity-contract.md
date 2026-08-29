# Gruntz parity contract for the RoM1 decompilation

Status: implemented contract, 2026-08-29

This project will use the Gruntz decompilation environment as its upstream
implementation, not merely as inspiration. The goal is that a contributor who
already knows Gruntz encounters the same shell layout, commands, files, build
graph, evidence model, matching loop, gates, and banking rules here.

Target-specific facts will change. Infrastructure behavior will not change
unless an explicit, reviewed compatibility seam makes exact reuse impossible.

## Upstream authority

The initial import is pinned to this committed Gruntz state:

| Field | Value |
| --- | --- |
| Repository | `https://github.com/sushi-shi/gruntz-decomp.git` |
| Commit | `00960e4a9beb6dfbf3f7e604bd5050ef8bf5e078` |
| Branch at audit | `main`, 64 commits ahead of `origin/main` |
| Audit date | 2026-08-29 |

The local Gruntz worktree was dirty during the audit. Its modified README,
review ledger, headers, and sources are not part of this pin. All imports must
come from the commit object above, never by copying the live worktree.

The pin is immutable for a given RoM1 infrastructure revision. Moving it is a
separate, reviewed upstream-sync change with a generated old/new parity report.

## Classification of every imported surface

Every Gruntz-to-RoM1 mapping must have exactly one class in
`config/gruntz_parity.tsv`:

| Class | Meaning | Allowed change |
| --- | --- | --- |
| `exact` | Infrastructure is target-independent | Byte-identical file from the pinned commit |
| `rename` | Infrastructure is identical after namespacing | Only declared token/path substitutions |
| `target` | Same schema and consumer behavior, different evidence | RoM1 rows or constants in the unchanged schema |
| `seam` | Exact reuse is technically impossible | Small isolated adapter, rationale, tests, and proof required |
| `excluded` | A Gruntz-only adjunct has no RoM1 input yet | Explicitly absent or disabled; no replacement is invented |

The ledger columns will be:

```text
upstream_path	local_path	class	upstream_sha256	local_sha256	reason	proof
```

No imported or omitted file is allowed to be unclassified. A verifier will
check the ledger, the pinned Git object, canonicalized hashes for `rename`
files, and the allowlisted differences. A change that creates an undocumented
divergence fails `rom1 verify parity`.

The initial mechanical substitutions are limited to a checked table such as:

```text
gruntz -> rom1
Gruntz -> Rom1
GRUNTZ -> ROM1
GRUNTZ.EXE -> ALLODS.EXE
gruntz.res -> allods.res
```

Substitutions are path-aware and token-aware. They are not an unrestricted
search-and-replace, and they may not alter an algorithm, CLI shape, default,
exit code, or generated-file contract.

## Import boundary

The initial transplant includes the following current Gruntz surfaces from the
pinned commit:

- root build and editor configuration: `flake.nix`, `flake.lock`, `.clangd`,
  `.clang-format`, `.gitattributes`, `.gitignore`, and `.githooks/`;
- the Nix support tree and every locally carried Vostok/objdiff patch;
- `scripts/gruntz/` as one Python package, including its core, graph, labels,
  model, delink, compare, sema, LSP, Ghidra, resource, lineage, verification,
  walls, and permutation modules;
- the toolchain-release and Wine-prefix builders;
- configuration schemas and representative empty/bootstrap files for retail
  labels, providers, link order, referent overrides, match baselines, and review
  claims;
- `include/rva.h`, mechanically namespaced only where a project token occurs;
- the build-system, matching, compiler, configuration, contributor, and gate
  doctrine, including `AGENTS.md` and the current `.agents/skills/` matcher
  material;
- the complete verification/self-test suite, including all negative controls.

The import does not copy Gruntz reconstructed game sources, Gruntz evidence
rows, generated output, binaries, build directories, historical `.claude`
orchestration, or domain-specific assets/codecs as if they applied to RoM1.
Those omissions are explicit `target` or `excluded` ledger rows.

The current `inventory/` corpus remains evidence input. It is not promoted into
the authoritative build model without passing the same claim and validation
rules as evidence discovered after bootstrap.

## Nix and toolchain identity

The default and build development shells must have the same topology and
behavior as Gruntz. RoM1's current broad investigation toolbox will move intact
to an explicit `nix develop .#inventory` shell; it will not remain the default
shell and silently change the contributor experience.

The initial build environment preserves these Gruntz pins and patches exactly:

| Component | Pinned Gruntz identity |
| --- | --- |
| nixpkgs | `64c08a7ca051951c8eae34e3e3cb1e202fe36786` |
| rust-overlay | `6cddd512...` from the audited `flake.lock` |
| Vostok | Gruntz base `81d34b204a0384a92cf3b4c641a8430256b2922e` plus all 8 Gruntz patches and the declared native reloc-manifest backport below |
| objdiff | v3.7.3 / `6bcac60...` plus both local patches |
| Rust | nightly-2026-05-27, resolved as 1.98.0-nightly |
| Python | 3.13.13 in the audited shell |
| Ninja | 1.13.2 in the audited shell |
| LLVM/Clang | 21.1.8, including the unwrapped clang binary |
| Ghidra | 12.0.4 |
| Wine | staging 11.8 |
| Java | JDK 21 used by the Gruntz shell |

The eight Gruntz patches remain byte-identical, including the Gruntz ILT
handling even though RoM1 currently appears non-incrementally linked. The only
additional Vostok delta is its own reviewed-relocation-manifest feature, ported
from local Vostok history with its tests. Keeping this delta isolated preserves
the Gruntz MSVC topology work while avoiding a different delinker architecture.

The shell package set, wrapper strategy, init behavior, Wine lifecycle, and
environment-variable set are copied. Mechanical project names are used:

```text
ROM1_DIR
ROM1_EXE
ROM1_CLANG
ROM1_TOOLCHAIN
ROM1_RUNTIME
MSVC_DIR
DXSDK_DIR
NINJA_DIR
GHIDRA_INSTALL_DIR
JAVA_HOME
LIBCLANG_PATH
PYTHONPATH
WINEPREFIX=$ROM1_DIR/build/wineprefix
WINEDEBUG=fixme-all,err-kerberos
WINEDLLOVERRIDES=mscoree,mshtml=
```

Like Gruntz, the wrapper resolves the repository/worktree root rather than
assuming the caller's current directory. The shell installs the repository Git
hooks, starts the same persistent Wine arrangement, cleans it up on interactive
shell exit, and automatically runs `rom1 init` unless the mechanically renamed
skip variable is set. The `play` shell uses a distinct runtime prefix.

The audited Gruntz VC5 package is the first compiler candidate. Its important
binary hashes are retained in the environment manifest:

| Binary | SHA-256 |
| --- | --- |
| `CL.EXE` | `bf9f9c74f756fed96e13f7f9a4273495c7dde0a1fb968e3ef6d760ad6d73dfeb` |
| `c1.dll` | `7f12a4a889c5a0277f12c391ca462657dc81ef7be769faf629331bd117983d5d` |
| `c1xx.dll` | `e27df3bb9a37058c85dad3fb7d1ed30b9e52d38fb6c0f66c8fdba0a11111d3d9` |
| `c2.exe` | `e75aecaf4073b0817ffb638cae5fff636b2e2d1a090daabf8f68dbc954515fae` |
| `link.exe` | `04c892989f4cc8076ef45e033215eb7aefbdf1459cbee9b13a81f8ddb718b579` |
| `cvtres.exe` | `16a45886f9257d990a9478c32ee6c1cbf4ac1fbcf889e5755960539233962465` |

That package was produced by Gruntz's reproducible toolchain-release script:
VS97 Disc 3, English SP3 overlays, required PDB/runtime/resource tools, and
Ninja, packed with fixed metadata. RoM1 replaces only its SDK layer with the
exact DirectX 5 distribution.

RoM1's PE header reports linker 5.02 and contains no Rich header, while the
Gruntz target proved its SP3 tool identities. RoM1's linker stamp hard-rejects
SP3 and retains SP1/SP2. Compile/link operations remain gated until a complete
byte-level witness panel selects and hashes one of those payloads. Shell
construction and path behavior remain the same.

## Command contract

The umbrella command remains one command with the Gruntz verb layout and return
semantics, mechanically renamed to `rom1`:

```text
rom1 tool
rom1 labels
rom1 model
rom1 delink
rom1 build
rom1 link
rom1 match
rom1 play
rom1 configure
rom1 sema
rom1 walls
rom1 lineage
rom1 permute
rom1 ghidra
rom1 verify
rom1 rsrc
rom1 lsp
rom1 init
```

The subcommand trees, option names, defaults, help ordering, stdout/stderr
roles, and exit codes are canonicalized and compared against Gruntz. In
particular:

- `rom1 sema` is a read-only assembly comparison command, accepts batch input
  through `rom1 sema -`, and preserves exit codes 0/1/2;
- Ghidra remains a one-way viewer and never becomes an authoritative editing
  database;
- `rom1 match` reports content-changed units and preserves per-function source
  fingerprints, RVA identity, current/best/historical scores, and ratchets;
- match banking stays manual and refuses to bank while build inputs contain
  unstaged changes;
- candidate linking remains opt-in, never part of the normal matching path;
- permutation and wall tools retain their Gruntz workflow rather than gaining
  RoM-specific shortcuts.

## Build graph and generated paths

The emitted Ninja DAG is structurally identical to Gruntz:

```text
config/units.toml
  -> build/build.ninja
  -> build/objdiff/base/<unit>.obj
  -> build/clangd/compile_commands.json
  -> build/gen/claims/<unit>.tsv
  -> build/gen/bindings.tsv + build/gen/violations.tsv
  -> synthesized PDB and manifests
  -> Vostok delink
  -> build/delink/named
  -> build/objdiff/target-new
  -> disposable normalization
  -> build/objdiff/compare-new
  -> objdiff.json
  -> report.json
  -> fingerprints
  -> default verification
```

The rule names, dependencies, depfiles, pools, pool depths, `restat` behavior,
write-if-changed behavior, toolchain identity input, and stamp behavior are
preserved. The Wine compiler pool remains depth 8. The canonical identities
remain:

```text
build/gen/toolchain.id
build/gen/.delink.stamp
build/gen/.normalize.stamp
```

If the exact Gruntz paths place a stamp elsewhere, the import follows the code,
not this prose. Generated output is disposable and ignored by Git.

The build aliases remain `base`, `claims`, `target`, `compare`, `verify`, and
`all`, with `all` as the default and `candidate` opt-in. Target names change
mechanically to `build/exe/ALLODS.candidate.EXE`, its map, and
`build/gen/allods.res`.

The paired-copy normalization rule is unchanged: authoritative compiler and
delinker output is not edited in place. Normalization happens only in the two
disposable comparison trees so both sides receive identical treatment.

## Configuration contract

`config/units.toml` retains the Gruntz schema:

```toml
[build]
compiler = "..."
platform = "..."

[flags]
# named complete flag profiles

[[unit]]
unit = "..."
source = "..."
flags = "..."
```

Each named flag profile is a complete command line. Per-TU bolt-ons are not
introduced. Gruntz's current profiles are copied as calibration candidates, not
asserted as RoM1 facts:

```text
c             /nologo /c /O2 /MT
cpp           /nologo /c /O2 /MT /GX
cpp-rtti      /nologo /c /O2 /MT /GX /GR
cpp-rtti-noeh /nologo /c /O2 /MT /GR
cpp-noeh      /nologo /c /O2 /MT
```

RoM1's inventory suggests `/O2 /Oy /MT /GX`, static MFC, and little or no game
RTTI. Those are hypotheses to test by TU; they do not justify changing the
schema or blanket-enabling `/GR`.

The evidence channels preserve Gruntz headers and semantics:

| File | Schema role |
| --- | --- |
| `config/retail/functions.tsv` | `rva kind` authoritative function census |
| `config/retail/data.tsv` | `rva kind` authoritative data census |
| `config/retail/relocs.tsv` | Vostok `site_rva kind` DIR32 site manifest for a fixed-base image |
| `config/functions_static_libs.tsv` | `rva name lib confidence source` |
| `config/functions_zlib.tsv` | `rva name unit size` |
| `config/data_vtables.tsv` | `rva size name kind note` |
| `config/data_static_libs.tsv` | `rva size name unit note` |
| `config/data_zlib.tsv` | `rva name unit size` |
| `config/data_compgen.tsv` | `rva size name owner class` |
| `config/link_order.tsv` | `seq unit start end class module n evidence notes` |
| `config/link_bands.tsv` | `lo hi band note` |
| `config/reloc_referents.tsv` | exact site/owner/addend/provenance override channel |
| `config/match_baseline.tsv` | unit and function score/fingerprint ratchets |
| review ledger | source hash, status, wall class, and evidence |

Provider filenames whose names describe a library not present in RoM1 remain
empty or are mechanically given a schema-equivalent target name. A schema
change is not allowed merely to make the filenames prettier.

`include/rva.h` keeps the Gruntz behavior: its labels are inert for VC5 and
emit clang metadata only under the metadata build. The function, data,
compiler-generated, dynamic-initializer, and override macros keep identical
meaning.

## Verification and non-vacuity

The full Gruntz verification suite is imported before RoM1 checks are relaxed
or rebased. The audited `verify/selftest.py` is 5,959 lines and contains more
than 50 negative-control classes. Test class/method rosters are compared to the
pinned upstream after namespacing.

The gate tiers and their default/opt-in status remain:

| Tier | Checks |
| --- | --- |
| Fast/default | board, vtable bans, casts, compiler artifacts, enum domains, label style, include order |
| Normal/default | unique names, library overlap, TU order, data TU order, dead code, undefined closure, review claims, data relocs, data access, data coverage |
| Full/opt-in | vtables, allocation size, assert relocs, caller-callee |
| Link/opt-in | link tier |

A target fixture may be rebased, but a check is not accepted until its clean
fixture passes and at least one intentional violation makes it fail for the
expected reason. Empty configuration, no discovered entities, or a skipped
tool cannot count as a passing gate. This is the non-vacuity rule.

## Matching and contribution process

The contributor loop is the Gruntz loop:

1. Locate the retail function and prove its exact start and extent.
2. Claim the RVA in the source and authoritative ledgers.
3. Reconstruct source under the byte-calibrated full TU profile.
4. Build through the emitted Ninja graph.
5. Compare raw and normalized output with `rom1 sema` and objdiff.
6. Inspect referents, relocations, compiler-generated artifacts, and whole-TU
   effects; do not explain mismatches solely from masked similarity.
7. Iterate without binary patching, inline assembly, fake relocation steering,
   or semantic distortions made only to game the score.
8. Run the required verification tiers.
9. Bank only a real improvement, preserving current/best/historical ratchets and
   source fingerprints.
10. Declare a function or TU exact only at byte equality with all ownership,
    references, generated artifacts, and gates closed.

One source of truth feeds labels, bindings, delinking, comparison, reporting,
and verification. Parallel hand-maintained maps are not introduced.

## Target-specific compatibility seams

Initially there is one small proven Vostok-input seam and one conditional
compiler seam.

### Required: Vostok-native relocation manifest

The selected RoM1 retail executable has `IMAGE_FILE_RELOCS_STRIPPED`, a zero
base-relocation data directory, and no `.reloc` section. The local Vostok
delinker already supplies both halves needed for this case:

- `scripts/find_relocs.py` at local Vostok commit
  `912a0aca03f3e7e188ba2fc057dab00ff081c4bb` performs site-anchored recovery;
- Vostok's `--reloc-manifest` consumes an authoritative byte-oriented TSV with
  the exact header `site_rva<TAB>kind` and `dir32` rows.

The generator is copied byte-for-byte from that Vostok commit. The manifest
consumer and its parser tests are backported onto the Gruntz Vostok base as the
smallest declared seam; Vostok's upstream behavior and file format are not
reimplemented in the RoM1 Python package.

The retail executable remains untouched. There is no synthesized PE and no
locally invented `.reloc` format. The tracked result is:

```text
config/retail/relocs.tsv
site_rva	kind
0x1003	dir32
...
```

The initial sweep has already been generated with Vostok's default channels and
filters: 32,454 kept sites, 4,373 candidates dropped as `unmapped` or
`data/code-isolated`, 32,457 file lines, and manifest SHA-256
`6080243236d478ba0df2b5b2b0dced13874f1d6f3b02a03bae6db6062ba5c3e7`.

Regeneration invokes the Vostok script, writes a candidate to `build/`, compares
it with `config/retail/relocs.tsv`, and replaces the tracked file only through
an explicit write action. The generated manifest is target evidence, not a
hand-maintained map. Target-specific proven false positives/negatives, if any,
use reviewed inclusion/exclusion inputs around the generic sweep rather than
edits to Vostok's algorithm.

The generator's `--validate` mode is run against the closest suitable local
non-stripped PE to report precision and recall by channel. That is calibration
of the generic rules, not a requirement to copy another executable's sites.
Vostok then reads the unchanged retail PE together with
`--reloc-manifest config/retail/relocs.tsv`.

### Conditional: compiler payload

The shell and release construction stay exact. Only the compiler payload may
differ if a representative witness panel proves that the pinned Gruntz VC5 SP3
payload cannot reproduce RoM1 and another exact, redistributable payload can.
Such a change records binary hashes, provenance, version witnesses, comparison
results, and a negative control.

## Explicitly forbidden drift

The following require a contract amendment rather than an ordinary coding
change:

- replacing the umbrella CLI with direct scripts or a new task runner;
- changing default gates, score meanings, baseline/banking rules, or exit codes;
- changing generated paths, build aliases, normalization ownership, or Wine
  prefix behavior for convenience;
- introducing per-TU flag fragments instead of full named profiles;
- using Ghidra, radare2, or inventory output as an unreviewed source of truth;
- weakening or deleting negative controls because RoM1 has not populated the
  corresponding evidence yet;
- patching Vostok or objdiff beyond the declared, upstream-derived
  reloc-manifest backport when a target-side input can preserve the pinned
  tools;
- copying generated files, raw game binaries, or local Gruntz worktree edits
  into version control;
- adding a RoM-only shortcut without a `seam` ledger entry and parity test.

This contract deliberately makes sameness testable. Familiarity is not left to
code-review intuition.
