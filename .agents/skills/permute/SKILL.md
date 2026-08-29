---
name: permute
description: Run classified Rom1 permutation campaigns as bounded N-island/M-frontier approximation searches, then inspect diverse high-scoring compiler states and translate their clues into authentic source changes. Use when a reconstructed function is complete but below 100%, when asked to search for higher fuzzy states, when several walls need permutation-candidate classification, or when an exact disposable TU-state result must be understood rather than copied.
---

# Permute

Use permutation as an evidence loop after reconstruction and wall classification.
The objective remains exact retail structure, not the highest fuzzy spelling.
Never retain generated declarations, fake locals, volatile carriers, or unexplained
source distortions.

## Establish the live population

Work in `nix develop .#build`. Build first when current objects may be stale, then
derive candidates rather than keeping a manual list:

```sh
rom1 build
rom1 permute candidates --output /tmp/permute-candidates.json
```

The command classifies normalized base/retail pairs by their first divergence.
Exclude EH funclets unless explicitly investigating EH. Use proven-at-100 current
dips for compiler-state replay, and high-current unproven functions for quick
pattern discovery. This campaign priority does not replace the low-historical-MAX
order used for canonical reconstruction.

## Run N islands and retain M distinct states

Start with 32 islands and a four-state frontier; specify RVAs when auditing a
chosen band:

```sh
rom1 permute campaign --rva 0x160450 --islands 32 --frontier 4 \
  --output /tmp/permute-160450
```

For several candidates, repeat `--rva` or use `--targets N`. Increase islands or
source depth only after inspecting the previous frontier. The campaign crosses
deterministic compiler-state islands with class-appropriate, semantics-preserving
AST shapes. It continues after an exact result so M useful alternatives can be
retained.

Treat states as different only when their normalized target instruction and
ordered-relocation identities differ. Different probe text that produces the
same state is one solution. Ranking is fuzzy first, then retail size and
relocation-count distance; topology remains a separate structural clue.

## Inspect the frontier

Read `campaign.json`, each result's `frontier/frontier.json`, `retail.asm`, and
the retained candidate source/assembly. For each of the best three or four
distinct states:

1. Find its first real divergence from retail.
2. Compare what moved across the frontier: call set, branch skeleton, operand
   order, live range, stack slot, register, or relocation identity.
3. Inspect callers, callees, types, storage, and the authored function before
   proposing a source explanation.
4. State the reusable hypothesis in source terms, such as corrected ownership,
   lifetime, declaration order, first post-call use, control-flow shape, or an
   inlining boundary.

Route a referent frontier back to identity evidence. Route call-set differences
to inline reconstruction. Route branch/return changes to CFG reconstruction.
Use permutation directly for a proven regalloc/scheduling residue. Follow the
`wall-identifier` and `matcher` skills for those investigations.

## Apply one source A/B and repeat

Implement only an evidence-backed, semantically defensible source change. Never
copy an `exact-disposable.cpp` TU-state forest into source. Compile and compare
the authored change, then rerun the campaign so the next frontier is conditioned
on the improved reconstruction.

An exact candidate closes the search only when score, extent, full decoding, and
ordered relocation identity all pass. A sub-100 improvement is a clue, not a
commit criterion. Keep correct modeling changes even if unrelated current fuzzy
moves, subject to the MAX gate.

Before handoff, run the focused permuter tests and a full build. Document a newly
reproducible compiler mechanism under `docs/patterns/` and update its index.
Commit tooling, documentation/skill work, and reconstructed source changes in
separate focused batches. See `docs/permuter.md` for command details and artifact
contracts.
