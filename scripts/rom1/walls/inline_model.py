#!/usr/bin/env python3
"""rom1.walls.inline_model - the cl 5.0 per-caller inline-budget model.

Executable model of MSVC's sequential inline-budget pass, ported from the
sibling HoMM3 project (homm3-decomp/scripts/homm3/vc6/inline_model.py), where
the mechanism and every constant were reverse-engineered from VC6's C2.DLL
(the rva comments below cite that provenance ledger, docs/vc6/inliner.md).
RE-VALIDATED on our pinned cl 5.0 SP3 by measurement:
docs/patterns/inline-budget-emits-ool-comdat.md.

    budget = clamp(2 * cb(caller), 1000, 35000)     # cb = front-end estimate
    spent sequentially in tuple order; cb <= 0x28 is budget-exempt;
    nested expansions get truncated budget / sites-remaining.

Where cl 5.0 diverges from the VC6 model (measured; do NOT port these back):
  * `/O2` implies `/Ob1`: an UNMARKED function is never a candidate at any
    definition position. Candidacy = inline-declared (or in-class body) AND
    the collector's cb < 1000 gate. Build `Callee(candidate=...)` from THAT
    rule, not from VC6's /Ob2 auto-inline heuristics.
  * VC6's front-end body-save cliff (all sites become calls at ~S=14) does
    NOT exist on cl 5.0 - the staircase continues (25,25,20,16,11,9,6,5 for
    S=1..13 agrees on both compilers, and cl 5.0 keeps going).
  * `#pragma inline_depth` is ignored by cl 5.0 at /O2 EXCEPT the one live
    lever documented in docs/patterns/msvc5-inline-depth-zero-is-the-only-
    live-lever.md - depth_allow below models the mechanism, not that pragma.

USAGE
    rom1 walls inline-model --selftest
    rom1 walls inline-model --spec sites.json [--json]
    rom1 walls inline-model --gap sites.json  [--json]
    rom1 walls inline-model --gap 0x08b960    # the address form: call-set
                                      # delta + base-obj symbol evidence;
                                      # undefined/absent remains ambiguous
    rom1 walls inline-model --measure-cb h.cpp --fn CALLEE \\
        --caller CALLER --sites N     # titrate cb with the real cl 5.0
                                      # (harness: --gen-harness)

spec JSON: {"caller_cb": N, "sites": [{"name": .., "cb": N, "sites": [..],
"forceinline": false, "marked": false, "candidate": true}, ..]}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from rom1.core.paths import BUILD

BUDGET_FLOOR = 1000    # VC6 0x19970: budget = max(2*caller_cb, 1000)
BUDGET_CAP = 35000     # VC6 0x199da -> cold stub: mov eax,0x88b8
RUNNING_CAP = 35000    # VC6 0x19f9f: running estimate cap
SMALL_FREE = 0x28      # cb <= 40 skips the budget entirely
CANDIDACY_CB = 1000    # collector gate: cb >= 1000 is never queued
DEPTH_DEFAULT = 8      # site depth allowance (see module docstring)


def _i16(v: int) -> int:
    """The IL size estimate is a SIGNED 16-bit field - huge front-end
    estimates wrap negative and revert the budget to the floor."""
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def _tdiv(a: int, b: int) -> int:
    """cdq+idiv truncates toward zero, unlike Python's floor division."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


class Callee:
    """A callee as the back end sees it: the front-end size estimate that
    feeds the decision, plus its stored body's own candidate call sites
    (re-decided at every expansion)."""

    def __init__(self, name, cb, sites=(), forceinline=False, marked=False,
                 candidate=True):
        self.name = name
        self.cb = cb                    # front-end size estimate
        self.sites = list(sites)        # candidate Sites inside the body
        self.forceinline = forceinline
        self.marked = marked            # inline-declared
        self.candidate = candidate      # cl 5.0: inline-marked AND cb < 1000


class Site:
    def __init__(self, callee, depth_allow=DEPTH_DEFAULT):
        self.callee = callee
        self.depth_allow = depth_allow


def _expand(sites, depth, budget, state, out):
    """The sequential accept loop. Returns (spent, budget)."""
    budget0 = budget
    n = len(sites)
    for k, site in enumerate(sites):
        nrem = n - k
        c = site.callee
        cb = _i16(c.cb)
        node = {"name": c.name, "cb": cb, "depth": depth,
                "budget_before": budget, "nested": []}
        out.append(node)
        if not c.candidate:
            node.update(action="call", reason="not-a-candidate "
                        "(unmarked under /Ob1, or cb>=1000)")
            continue
        if depth > site.depth_allow:
            node.update(action="call", reason="depth")
            continue
        if not c.forceinline:
            if budget < cb and cb > SMALL_FREE:
                node.update(action="call", reason="budget")
                continue
            if state["running"] > RUNNING_CAP:
                node.update(action="call", reason="running-cap")
                continue
        if not c.forceinline:
            if cb > SMALL_FREE:
                budget -= cb
            state["running"] += cb
        sub_budget = _tdiv(budget, nrem)
        spent, _ = _expand(c.sites, depth + 1, sub_budget, state,
                           node["nested"])
        if not c.forceinline:
            budget -= spent
            state["running"] += spent
        node.update(action="expand", reason="")
    return budget0 - budget, budget


def predict(caller_cb, sites):
    """Pure model of one function's inline pass.

    caller_cb: the CALLER's own front-end size estimate.
    sites: the caller's candidate call Sites in tuple-stream order (both
    branch arms - the collector walks the stream linearly).
    Returns {budget, decisions, spent, ...}."""
    cb = _i16(caller_cb)
    budget = 2 * cb
    if budget < BUDGET_FLOOR:
        budget = BUDGET_FLOOR
    elif budget > BUDGET_CAP:
        budget = BUDGET_CAP
    state = {"running": cb}
    decisions: list = []
    spent, left = _expand(sites, 1, budget, state, decisions)
    return {"caller_cb": cb, "budget": budget, "spent": spent,
            "budget_left": left, "running_final": state["running"],
            "decisions": decisions}


# cb per simple statement (measured by titration; approximate - ballpark gaps
# only). The budget floor breaks at ~36-40 caller statements, which matches
# the pattern doc's measured break.
CB_PER_STMT = 14


def budget_gap(caller_cb, sites):
    """For each budget-STARVED site, how much more caller body would expand
    it. budget = 2*caller_cb, so raising the caller's cb by ceil(deficit/2)
    lifts the site's budget by `deficit` - the 'finish the caller' lever,
    quantified. The FIRST starved site is the cleanest target (sequential
    spending moves the later ones together)."""
    rep = predict(caller_cb, sites)
    gaps = []
    for _depth, d in _flatten(rep["decisions"]):
        if d["action"] == "call" and d["reason"] == "budget":
            deficit = d["cb"] - d["budget_before"]
            gaps.append({
                "callee": d["name"], "cb": d["cb"],
                "budget_at_site": d["budget_before"],
                "deficit_cb": deficit,
                "grow_caller_cb_by": (deficit + 1) // 2,
                "approx_caller_statements": max(
                    1, round((deficit / 2) / CB_PER_STMT))})
    return {"budget": rep["budget"], "at_floor": rep["budget"] == BUDGET_FLOOR,
            "spent": rep["spent"], "starved_sites": gaps, "report": rep}


def _flatten(decisions, depth=0):
    for d in decisions:
        yield depth, d
        yield from _flatten(d["nested"], depth + 1)


def _print_report(rep) -> None:
    print(f"[model] caller_cb={rep['caller_cb']}  budget=2*cb clamped to "
          f"[{BUDGET_FLOOR},{BUDGET_CAP}] = {rep['budget']}  "
          f"spent={rep['spent']}  left={rep['budget_left']}  "
          f"running(final)={rep['running_final']}")
    for depth, d in _flatten(rep["decisions"]):
        mark = "EXPAND" if d["action"] == "expand" else "call  "
        why = f"  ({d['reason']})" if d["reason"] else ""
        print(f"  {'  ' * depth}{mark} {d['name']}  cb={d['cb']} "
              f"budget@site={d['budget_before']}{why}")


def _counts(rep, name):
    ex = sum(1 for _, d in _flatten(rep["decisions"])
             if d["name"] == name and d["action"] == "expand")
    ca = sum(1 for _, d in _flatten(rep["decisions"])
             if d["name"] == name and d["action"] == "call")
    return ex, ca


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


# --------------------------------------------------------------------------- #
# --measure-cb: titrate a callee's cb with the REAL cl 5.0. The harness TU
# (--gen-harness S N PAD) contains the callee and a caller with
# N same-callee sites; with a small caller the budget is the 1000 floor, so
#     expanded = floor(1000 / cb)   (cb > 40; 0 expanded = not a candidate)
# and counting REJECTED sites (call + tail-jmp) brackets cb.
# --------------------------------------------------------------------------- #

_PROFILE = ["/O2", "/MT", "/GX", "/GR", "/FAs"]
_MODEL_SCRATCH = BUILD / "inline-model"


def measure_cb(src: Path, callee: str, caller: str, n_sites: int):
    """Compile the harness TU; return (expanded, rejected, lo, hi) where
    cb in [lo, hi] (lo=None => cb <= 40; hi=None => not a candidate)."""
    from rom1.tool import ToolError, cl
    _MODEL_SCRATCH.mkdir(parents=True, exist_ok=True)
    out = _MODEL_SCRATCH / (src.stem + ".obj")
    try:
        cl.compile(src, out, ["/nologo", "/c", *_PROFILE])
    except ToolError as e:
        die(f"measure-cb compile failed: {e}")
    # cl drops the /FAs listing beside the OBJECT it writes (cwd=out.parent)
    asm = out.with_suffix(".asm")
    if not asm.is_file():
        asm = _MODEL_SCRATCH / (src.stem + ".asm")
    if not asm.is_file():
        die(f"measure-cb: no /FAs listing beside {out.name}")
    body, inside = [], False
    for line in asm.read_text(errors="replace").splitlines():
        if not inside and caller in line and " PROC" in line:
            inside = True
        elif inside:
            if " ENDP" in line:
                break
            body.append(line)
    text = "\n".join(body)
    rejected = len(re.findall(r"\b(?:call|jmp)\s+[^\n;]*" + re.escape(callee),
                              text))
    expanded = n_sites - rejected
    if expanded < 0:
        die(f"measure-cb: found {rejected} call/jmp site(s) to {callee} in "
            f"{caller}, more than --sites {n_sites}. Pass --sites {rejected} "
            f"(or check the mangled name - a tail `jmp` to the callee counts "
            f"as a rejection too).")
    if expanded == n_sites:
        lo, hi = None, SMALL_FREE       # never rejected: cb <= 40 (or the
        #                                 budget never bound - use more sites)
    elif expanded == 0:
        lo, hi = CANDIDACY_CB, None     # not a candidate (or cb > budget)
    else:
        lo = BUDGET_FLOOR // (expanded + 1) + 1
        hi = BUDGET_FLOOR // expanded
    return expanded, rejected, lo, hi


# --------------------------------------------------------------------------- #
# --selftest: model-arithmetic regressions. The oracle data is the sibling
# project's measured pinned-compiler corpus; the cl 5.0 re-validation of the
# shared mechanics is docs/patterns/inline-budget-emits-ool-comdat.md.
# --------------------------------------------------------------------------- #

def _selftest() -> int:
    failures = []

    def check(label, ok, detail=""):
        print(f"[selftest] {'PASS' if ok else 'FAIL'}  {label}"
              + (f"  {detail}" if detail else ""))
        if not ok:
            failures.append(label)

    # 1. 9 sites, small caller -> 6 expand + 3 reject across cb=[143,166].
    ok = all(_counts(predict(120, [Site(Callee("fill", cb))] * 9), "fill")
             == (6, 3) for cb in range(143, 167))
    check("fill 6+3 across cb=[143,166]", ok)

    # 2. candidate=False -> every site is a call. (On cl 5.0 the flag comes
    #    from /Ob1 candidacy - unmarked fn or cb>=1000 - not VC6's save gate.)
    rep = predict(120, [Site(Callee("filsd", 170, candidate=False))] * 9)
    check("candidacy drop 0+9", _counts(rep, "filsd") == (0, 9))

    # 3. cb <= 40 is budget-exempt -> 60/60 expand.
    rep = predict(60, [Site(Callee("tiny", 20))] * 60)
    check("small-free 60/60", _counts(rep, "tiny") == (60, 0))

    # 4. nested: 6x gg -> 3x hh each; budget/nrem at the nested level gives
    #    exactly ONE hh per gg copy across cb(hh)=[143,166].
    ok = True
    for cbh in range(143, 167):
        gg = Callee("gg", 30, sites=[Site(Callee("hh", cbh))] * 3)
        rep = predict(60, [Site(gg)] * 6)
        ok &= _counts(rep, "gg") == (6, 0) and _counts(rep, "hh") == (6, 12)
    check("nested 6/0 gg + 6/12 hh across cb(hh)=[143,166]", ok)

    # 5. caller-size coupling: padding the CALLER (cb 930) lifts the budget
    #    to 1860 >= 9*cb(fill) -> all 9 expand.
    rep = predict(930, [Site(Callee("fill", 150))] * 9)
    check("pad flip 9/0 at caller_cb=930", _counts(rep, "fill") == (9, 0))

    # 6. int16 wrap: caller_cb > 32767 wraps negative -> floor budget.
    rep = predict(40000, [Site(Callee("fill", 150))] * 9)
    check("int16 wrap reverts to floor budget 6/3",
          _counts(rep, "fill") == (6, 3))

    # 7. STL flip shape: 12 ctor trees charge the budget up front; the divided
    #    budget starves every nested _Tidy except the last site; a padded
    #    caller expands all 24.
    def ctor():
        return Callee("ctor", 60, sites=[Site(Callee("_Tidy", 85))])

    def dtor():
        return Callee("dtor", 20, sites=[Site(Callee("_Tidy", 85))])

    def shape():
        return [Site(ctor()) for _ in range(12)] + \
               [Site(dtor()) for _ in range(12)]
    small = predict(80, shape())
    big = predict(3500, shape())
    s_ex, s_ca = _counts(small, "_Tidy")
    b_ex, b_ca = _counts(big, "_Tidy")
    check("STL flip: small caller starves _Tidy, padded caller 24/0",
          s_ca >= 20 and (b_ex, b_ca) == (24, 0),
          f"small={s_ex}/{s_ca} big={b_ex}/{b_ca}")

    # 8. knife-edge: a mid-budget subtree spend flips a later duplicate site
    #    between expand and call; a larger caller estimate expands both.
    ok = True
    flip_ok = True
    for cbgt in (46, 47):
        for cbk in range(77, 84):
            for id_spend in range(710, 787, 25):
                def kill():
                    return Callee("kill", cbk,
                                  sites=[Site(Callee("get_total", cbgt))])
                idmg = Callee("inflict_damage", id_spend, candidate=True)
                sites = [Site(kill()), Site(idmg), Site(kill()), Site(idmg)]
                rep = predict(235, sites)
                ok &= _counts(rep, "get_total") == (1, 1)
                rep2 = predict(1400, sites)
                flip_ok &= _counts(rep2, "get_total") == (2, 0)
    check("knife-edge: expand@copy1 + call@copy2 (small caller)", ok)
    check("knife-edge: larger caller_cb expands both", flip_ok)

    if failures:
        print(f"[selftest] {len(failures)} FAILURE(S): " + ", ".join(failures))
    else:
        print("[selftest] ALL PASS")
    return 1 if failures else 0


SPEC_SHAPE = ('{"caller_cb": N, "sites": [{"name": "callee", "cb": N, '
              '"sites": [...], "candidate": true}, ...]}')


def _load_spec(path: Path):
    try:
        spec = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON ({e}); expected {SPEC_SHAPE}")
    for key in ("caller_cb", "sites"):
        if key not in spec:
            die(f"{path} has no {key!r} key; expected {SPEC_SHAPE}")

    def mk_site(s):
        c = s.get("callee", s)
        if "cb" not in c:
            die(f"{path}: a site has no 'cb' (the front-end size estimate); "
                f"expected {SPEC_SHAPE}")
        callee = Callee(c.get("name", "?"), c["cb"],
                        sites=[mk_site(x) for x in c.get("sites", [])],
                        forceinline=c.get("forceinline", False),
                        marked=c.get("marked", False),
                        candidate=c.get("candidate", True))
        return Site(callee, depth_allow=s.get("depth_allow", DEPTH_DEFAULT))

    return spec["caller_cb"], [mk_site(s) for s in spec["sites"]]


def gap_from_rva(token: str) -> int:
    """`--gap <rva>`: name the call-set delta and report candidacy evidence.

    CLAUDE.md points every inline/call-set wall at this verb, but the only form
    it had took a spec JSON of front-end `cb` estimates - numbers nobody has for
    a real row - so the documented lever could not be invoked at an address at
    all.  What IS exactly derivable from an address is the two questions that
    come BEFORE the budget arithmetic, and they decide whether the budget lever
    applies:

      1. WHICH callees differ, from the same normalized pair `walls diagnose`
         reads;
      2. what our own base obj's symbol table proves. A locally defined COMDAT
         positively proves inline visibility. An UNDEFINED symbol does not
         prove the opposite: a header inline may expand at one site and leave
         an external reference at a declined or nested site. An absent symbol
         is likewise consistent with every local site expanding. `/O2` still
         implies `/Ob1`; source declarations, an `/Ob0` census, or ordered
         call-site topology must settle the ambiguous cases.

    The `cb` arithmetic still needs `cb`, and this refuses to invent one:
    measure it with `--measure-cb` and pass a spec.  A guessed budget deficit
    printed as a model output would be indistinguishable from a measured one.
    """
    from collections import Counter

    from rom1.walls.diagnose import (
        NORM, _call_targets, _find_function, _jump_table_bytes, _locate,
        _skeleton,
    )
    from rom1.delink.coffx import Obj

    b, why = _locate(token)
    if b is None:
        die(why)
    base_p = NORM / "base" / f"{b.unit}.obj"
    tgt_p = next((p for p in (NORM / "target" / f"{b.unit}.c.obj",
                              NORM / "target" / f"{b.unit}.obj") if p.is_file()),
                 None)
    if not base_p.is_file() or tgt_p is None:
        die(f"normalized pair missing for {b.unit} - run `rom1 build` first")

    calls = {}
    for tag, path in (("base", base_p), ("target", tgt_p)):
        payload, rel, _size = _find_function(Obj(path), b.name)
        if payload is None:
            die(f"{tag} obj does not define {b.name}")
        _m, _c, _br, _r, _i, asm = _skeleton(
            payload, rel, data=_jump_table_bytes(rel, b.name))
        calls[tag] = Counter(n for n, _a in _call_targets(rel, asm, b.name))

    obj = Obj(base_p)
    symbols = {obj.sym_name(i) for i, _v, _sn in obj.iter_symbols()}
    defined = {obj.sym_name(i) for i, _v, sn in obj.iter_symbols() if sn > 0}

    print(f"[budget-gap] {b.name}  [{b.unit}]  rva 0x{b.rva:06x}")
    delta = [n for n in sorted(calls["base"].keys() | calls["target"].keys())
             if calls["base"][n] != calls["target"][n]]
    if not delta:
        print("  call-set delta: none - this row is not an inline/call-set "
              "wall, so the budget model has nothing to say about it.")
        return 0
    for n in delta:
        bn, tn = calls["base"][n], calls["target"][n]
        side = "base calls MORE" if bn > tn else "base calls FEWER"
        print(f"  {n}\n      target {tn}, base {bn}   ({side})")
        if bn > tn:
            if n in defined:
                print("      INLINE-VISIBLE: this TU emits its own COMDAT. "
                      "Candidacy is proved;\n"
                      "                      inspect site order, then measure "
                      "cb (`--measure-cb`) if\n"
                      "                      the delta is a declined expansion.")
            elif n in symbols:
                print("      AMBIGUOUS: UNDEFINED external in this obj. It may "
                      "be an ordinary out-of-line\n"
                      "                 function OR a visible header inline "
                      "with another declined/nested\n"
                      "                 reference. Inspect the declaration, "
                      "/Ob0 census, and site topology.")
            else:
                print("      AMBIGUOUS: no base symbol-table row. The call-set "
                      "delta alone cannot\n"
                      "                 distinguish a missing site from an "
                      "inline expansion; inspect source\n"
                      "                 visibility and ordered site topology.")
        else:
            if n in defined:
                print("      INLINE-VISIBLE: this TU emits its own COMDAT, and "
                      "base has fewer calls.\n"
                      "                      Expansion is possible, but compare "
                      "site topology before\n"
                      "                      attributing the delta to budget.")
            elif n in symbols:
                print("      AMBIGUOUS: UNDEFINED external in this obj does not "
                      "rule out a header-inline\n"
                      "                 expansion. It also does not rule out "
                      "tail sharing. Inspect the\n"
                      "                 declaration, /Ob0 census, and ordered "
                      "site topology.")
            else:
                print("      AMBIGUOUS: symbol absent from the base obj. This is "
                      "consistent with full\n"
                      "                 expansion OR with no corresponding "
                      "source site; compare the local\n"
                      "                 expansion and tail-sharing topology.")
    return 0


def gen_harness(statements: int, sites: int, pad: int) -> str:
    """The --measure-cb harness TU: a callee of S statements, a caller with N
    same-callee sites behind PAD statements of caller mass (folded in from the
    retired tools/inline-budget/gen_harness.py)."""
    body = "\n".join("    gA[%d] = gA[%d] + row;" % (i, i + 1)
                     for i in range(statements))
    padding = "\n".join("    gB[%d] = gB[%d] + p;" % (i % 60, (i + 1) % 60)
                        for i in range(pad))
    calls = "\n".join("    leaf(%d);" % i for i in range(sites))
    return ("int gA[256];\nint gB[256];\n\ninline void leaf(int row) {\n%s\n}\n\n"
            "void callerX(int p) {\n%s\n%s\n}\n" % (body, padding, calls))


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="rom1 walls inline-model",
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true",
                    help="replay the validated oracle cases through predict()")
    ap.add_argument("--spec", help="JSON caller/sites spec to predict")
    ap.add_argument("--gap", metavar="SPEC|RVA",
                    help="a JSON caller/sites spec: report the budget deficit "
                    "per starved site as CALLER statements. Or an rva/name: "
                    "name the call-set delta from the normalized pair and "
                    "screen each site's /Ob1 candidacy in our own base obj")
    ap.add_argument("--measure-cb", dest="measure_cb", metavar="TU",
                    help="titrate a callee's cb: compile TU, count rejected "
                    "sites in --caller")
    ap.add_argument("--fn", help="measure-cb: callee")
    ap.add_argument("--caller", help="measure-cb: harness caller function")
    ap.add_argument("--sites", type=int, help="measure-cb: site count")
    ap.add_argument("--gen-harness", nargs=3, type=int, metavar=("S", "N", "PAD"),
                    help="print a measure-cb harness TU: S callee statements, "
                         "N call sites, PAD caller statements ahead of them")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.gen_harness:
        print(gen_harness(*args.gen_harness), end="")
        return 0

    if args.selftest:
        return _selftest()
    if args.spec:
        if not Path(args.spec).is_file():
            die(f"spec JSON missing: {args.spec}")
        caller_cb, sites = _load_spec(Path(args.spec))
        rep = predict(caller_cb, sites)
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            _print_report(rep)
        return 0
    if args.measure_cb:
        src = Path(args.measure_cb).resolve()
        if not src.is_file():
            die(f"harness TU missing: {src} (`--gen-harness S N PAD` prints one)")
        if not (args.fn and args.caller and args.sites):
            die("--measure-cb needs --fn CALLEE --caller CALLER --sites N")
        ex, rej, lo, hi = measure_cb(src, args.fn, args.caller, args.sites)
        if lo is None:
            verdict = f"cb <= {SMALL_FREE} (never rejected; budget-exempt)"
        elif hi is None:
            verdict = f"NOT an inline candidate (/Ob1 unmarked, or cb >= {CANDIDACY_CB})"
        else:
            verdict = f"cb in [{lo},{hi}]"
        print(f"[measure-cb] {args.fn}: {ex} expanded, {rej} rejected "
              f"(call+jmp) of {args.sites} -> {verdict}")
        return 0
    if args.gap:
        if not Path(args.gap).is_file():
            if args.gap.endswith(".json"):
                die(f"spec JSON missing: {args.gap}")
            return gap_from_rva(args.gap)
        caller_cb, sites = _load_spec(Path(args.gap))
        g = budget_gap(caller_cb, sites)
        if args.json:
            print(json.dumps({k: v for k, v in g.items() if k != "report"},
                             indent=2))
            return 0
        floor = ("  (AT THE 1000 FLOOR - caller is small/starved)"
                 if g["at_floor"] else "")
        print(f"[budget-gap] budget={g['budget']}{floor}  spent={g['spent']}")
        if not g["starved_sites"]:
            print("  no budget-starved sites - inline structure is not "
                  "budget-limited here.")
        for s in g["starved_sites"]:
            print(f"  {s['callee'][:56]} cb={s['cb']}: budget "
                  f"{s['budget_at_site']} at site, short {s['deficit_cb']} -> "
                  f"grow the CALLER by ~{s['approx_caller_statements']} "
                  f"statement(s) (+{s['grow_caller_cb_by']} caller_cb)")
        return 0
    ap.error("need --selftest, --spec/--gap FILE, or --measure-cb TU")


if __name__ == "__main__":
    raise SystemExit(main())
