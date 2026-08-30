"""rom1 - the umbrella CLI.

    rom1 tool <name> [args...]     drive one external tool (rom1/tool/)
    rom1 labels [--all|--unit U]   source labels -> claim fragments (+ the
                                     tree-wide completeness sweep)
    rom1 model                     resolve claims x censuses -> bindings
    rom1 delink                    model -> synth pdb -> retail target objs
    rom1 compare                   base vs target -> objdiff report + summary
    rom1 build                     configure-if-needed + ninja (the loop:
                                     cl -> labels -> model -> delink -> compare)
    rom1 link                      the opt-in candidate link (EXE + .map)
    rom1 match                     build, then the compare summary for the
                                     units whose objs changed
    rom1 play                      build + link, install the candidate into
                                     the game env, run it under gamescope
                                     (integer-scaled; --retail = the control)
    rom1 configure                 re-emit build/build.ninja
    rom1 sema <sub>                read-only investigation views (disasm,
                                     xref, rva, vtable, classof, strings, ...)
    rom1 walls <sub>               the wall campaign: inventory, diagnose,
                                     inline-model
    rom1 lineage <sub>             discover, inventory and verify surviving
                                     LithTech source-lineage decisions
    rom1 permute <verb>            classified state/variant search or island campaign
    rom1 ghidra <sub>              one-way viewer export: the retail image
                                     as a labelled Ghidra project (build,
                                     update, verify, status, export)
    rom1 verify <sub>              status / check (the MAX gate) / bank
                                     (baseline + README, manual) /
                                     fingerprints
    rom1 rsrc check                compile Allods.rc with era rc.exe,
                                     byte-compare 75/75 vs the retail .rsrc
    rom1 lsp <verb>                clangd-backed refs / hover / rename (the
                                     type-aware bulk member renamer)
    rom1 init                      local setup (the build wine prefix; the
                                     dev-shell hook runs this at entry)

Subcommands grow with the rebuild; `tool` forwards to the named module's own
main(), so `rom1 tool cl ...` and `python3 -m rom1.tool.cl ...` (the form
ninja rule lines use) are the same entry.
"""

from __future__ import annotations

import sys

TOOLS = ("wine", "cl", "link", "rc", "delinker", "pdbutil", "objdiff",
         "objdump", "ghidra", "clangd", "rez", "relocs",
         "retail-census", "library-census", "compiler-census", "vendor",
         "retail-partition", "fid-census", "parity")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        print(f"\ntools: {', '.join(TOOLS)}")
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd in ("labels", "model", "delink", "compare"):
        import importlib
        mod = importlib.import_module(
            {"labels": "rom1.retail_labels.source", "model": "rom1.model",
             "delink": "rom1.delink.run", "compare": "rom1.compare.run"}[cmd])
        sys.argv = [f"rom1 {cmd}", *rest]
        return mod.main()
    if cmd in ("sema", "walls", "ghidra", "verify", "rsrc", "lsp", "lineage"):
        import importlib
        return importlib.import_module(f"rom1.{cmd}").main(rest)
    if cmd == "permute":
        if not rest or rest[0] in ("-h", "--help"):
            print("rom1 permute candidates [options]\n"
                  "rom1 permute campaign [--rva <rva>] [options]\n"
                  "rom1 permute state --source <tu.cpp> --rva <rva> [options]\n"
                  "rom1 permute variants <tu.cpp> <rva> [options]\n"
                  "  candidates: classify every live source-owned residual\n"
                  "  campaign: run N islands and retain M distinct best solutions\n"
                  "  state: classified, disposable compiler-state search\n"
                  "  variants: reviewed exact axes x AST shapes x TU state")
            return 0 if rest else 2
        if rest[0] in ("candidates", "campaign"):
            from rom1.permute.campaign import main as campaign_main
            return campaign_main(rest)
        if rest[0] not in ("state", "variants"):
            print("rom1 permute: unknown verb " + repr(rest[0])
                  + " (have: candidates, campaign, state, variants)", file=sys.stderr)
            return 2
        verb, permute_args = rest[0], rest[1:]
        if any(value in ("-h", "--help") for value in permute_args):
            if verb == "state":
                from rom1.permute.tu_state_noise import main as permute_main
            else:
                from rom1.permute.match_variants import main as permute_main
            return permute_main(permute_args)
        rva_arg = (
            next((
                permute_args[index + 1]
                for index, value in enumerate(permute_args[:-1])
                if value == "--rva"
            ), None)
            if verb == "state"
            else (permute_args[1] if len(permute_args) >= 2 else None)
        )
        if rva_arg is None:
            print(f"rom1 permute {verb}: an RVA is required", file=sys.stderr)
            return 2
        from contextlib import redirect_stdout
        from io import StringIO
        from rom1.walls.diagnose import diagnose
        diagnosis = StringIO()
        with redirect_stdout(diagnosis):
            result = diagnose(rva_arg)
        report = diagnosis.getvalue()
        print(report, end="")
        if result or "class: REGALLOC/SCHEDULING" not in report:
            print(f"rom1 permute {verb}: refused - permutation requires a "
                  "REGALLOC/SCHEDULING diagnosis", file=sys.stderr)
            return 2
        from rom1.model import resolve
        from rom1.verify.baseline import load as load_baseline
        rva = int(rva_arg, 0)
        if rva >= 0x400000:
            rva -= 0x400000
        binding = next((row for row in resolve().functions if row.rva == rva), None)
        bank = load_baseline().get((binding.unit, binding.name)) if binding else None
        if bank and bank["hist"] >= 100.0:
            print(f"rom1 permute {verb}: refused - historical MAX is already "
                  "100%", file=sys.stderr)
            return 2
        if verb == "state":
            from rom1.permute.tu_state_noise import main as permute_main
        else:
            from rom1.permute.match_variants import main as permute_main
        return permute_main(permute_args)
    if cmd in ("build", "link", "match", "play"):
        from rom1.graph.verbs import VERBS
        return VERBS[cmd](rest)
    if cmd == "configure":
        from rom1.graph.emit import main as configure
        sys.argv = ["rom1 configure", *rest]
        return configure()
    if cmd == "init":
        from rom1.tool import ToolError
        from rom1.tool.wine import init_prefix, verify_prefix
        try:
            init_prefix()
            verify_prefix()
        except ToolError as e:
            print(f"[init] {e}", file=sys.stderr)
            return 1
        print("[init] build wine prefix OK (the graph/init steps grow with "
              "the rebuild)")
        return 0
    if cmd == "tool":
        if not rest or rest[0] not in TOOLS:
            print(f"rom1 tool: pick one of {', '.join(TOOLS)}", file=sys.stderr)
            return 2
        import importlib
        mod = importlib.import_module(f"rom1.tool.{rest[0].replace('-', '_')}")
        sys.argv = [f"rom1 tool {rest[0]}", *rest[1:]]
        return mod.main()
    print(f"rom1: unknown command {cmd!r} (the rebuild grows these "
          "step by step; see scripts/rom1/__init__.py)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
