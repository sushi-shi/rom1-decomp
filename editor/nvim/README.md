# rom1.nvim

In-editor [objdiff](https://github.com/encounter/objdiff) for the **rom1**
binary-matching project. For the function under your cursor: its **target**
(retail) asm, its **base** (recompiled) asm, a **side-by-side diff**, and its
**match %** — without leaving Neovim to start the objdiff TUI. Plus a one-key
**build** that recompiles and tells you what moved.

Presentation only — no extra tool. Every asm/diff view is one
`objdiff-cli diff … --format json` invocation, and the function under the cursor
resolves through the data the pipeline already emits:

- `build/gen/symbol_names.csv` — the join table: retail address → mangled symbol
  + unit.
- `build/objdiff/report.json` — per-function match %.

The retail **address** in each function's `RVA(0x…, 0x…)` macro (see
`include/rva.h`) is the key. It moves with the function text, so cursor→function
resolution never goes stale — unlike line tables.

## Interface

`:Rom1 {target|base|diff|status|hints|autobuild|autoformat}` (tab-completable)
and `:Rom1Build [args]`.

Buffer-local chords on C/C++ buffers:

| chord | action                                                         |
|-------|----------------------------------------------------------------|
| `vt`  | **target** asm of the function at the cursor                   |
| `vb`  | **base** asm                                                   |
| `vd`  | **diff** — target ∣ base side-by-side (the "objdiff look")      |
| `vs`  | **status** — match-% overview, current unit's functions listed |
| `vx`  | **xrefs** — callers (thunk-chased) + callees of the fn at the cursor (`0x..` navigable with `<CR>`/`V`/`vg`) |
| `vi`  | **inheritance + vtable** of the class/`VTBL(..)` under the cursor (`sema class` slots + `--tree` spine) |
| `vg`  | **goto definition** — jump to the *source* def of the fn whose `0x..` is under the cursor (chases vtable-slot thunks; works in source, comments, and views) |
| `vB`  | **build** (`:Rom1Build`)                                     |
| `vq`  | **close** all open rom1 views                                |
| `V`   | **peek** — match % + metadata (size, rva, unit) in a float     |

`vt`/`vb`/`vd` keep the cursor in your source buffer (the view opens without
stealing focus), and a new view **replaces** the previous one (so `vd` on a new
function closes the old `vd`). The diff shows the **whole function** (folding off),
target on the left and base on the right.

- **target / base** open a reusable scratch split (`filetype=asm`, so mnemonics/
  registers/labels are syntax-highlighted); the header carries the symbol and its
  match %. Intra-function jump targets get synthetic labels (`.L1:` …) and
  branches reference them (`jne short .L1`) instead of raw offsets. When a **base**
  view is open and a build changes the base, it turns into a `previous build → now`
  diff — you see exactly what your edit did to the compiled output. (Target asm is
  fixed by the retail binary, so it just re-renders.)
- **diff** opens two scratch buffers in a native Neovim **diff** split (target
  left, base right): scrollbound, with diverging instructions highlighted. Each
  pane's winbar labels it `TARGET (retail)` / `BASE (recompiled)` with the % so
  the sides are never ambiguous. The jump labels also keep the diff tight — a
  branch matches on both sides even when its byte offset shifts.
- **status** lists every started unit by match % (worst first); the current
  file's unit is marked `>` and expanded to its functions. `<CR>` on a function
  row opens its diff.
- **peek** floats the current function's match % and metadata (size, retail
  address, unit progress) — instant, no objdiff call; inside any plugin view,
  `<CR>`/`V` instead follow a `0x…` (or status row) to that function's diff.
  `q` closes.

## Inline % hints

Like coc's inlay hints: every `RVA(0x…, 0x…)` line in a source buffer is tagged
with its function's match % as end-of-line virtual text, colored by how close it
is (`✓ 100%` green, partial yellow, low red, `— n/a` if not built). So the match
state is visible *as you read the code*, no command needed. Refreshed on
enter/save and after `:Rom1Build`. Toggle with `:Rom1 hints`, or disable by
default with `hints = false` in `setup`.

`:Rom1Log` shows the resolved `objdiff-cli` path and every invocation — handy
when a stale dev shell ships an old binary.

## `:Rom1Build` — build and report what moved

`vB` snapshots the current `report.json`, runs the build, and on success shows a
**compact corner popup** with the build time, the overall % change, and the
current unit's `before → after` deltas for the functions that moved (`↑`/`↓`/`+`,
capped — `vs` has the full table). The popup never steals focus (handy when the
async build lands while you're typing elsewhere) and fades after a few seconds.
Extra args pass through to the build, e.g. `:Rom1Build build/objdiff/base/netmgr.obj`
to limit ninja to one TU.

> **Launch nvim from `nix develop` for fast builds.** The build then runs
> `rom1 build` **directly** (~0.5–1s). Launched from the plain `nix develop`
> shell it still works, but each build is wrapped in `nix develop`, which
> adds ~2.5s of shell-setup overhead *per build*. The plugin auto-detects which
> shell it's in (via `$MSVC_DIR`).

### Build on save (`:Rom1 autobuild`)

Off by default. When on, **saving a TU** (`*.c`/`*.cpp`/`*.cc`) recompiles **only
that file's unit** and re-diffs it — **no log window**, just a small `building …`
corner note that closes into a result popup — so the **inline %s update right
after you save** (and any open `vd`/`vt`/`vb` view for that unit re-renders in
place, keeping your cursor and scroll). The tight loop: edit a function, `:w`,
watch its `%` move. Enable per session with `:Rom1 autobuild`, or by default
with `build_on_save = true` in `setup`. **Rapid saves supersede:** a new save
cancels the in-flight one (latest wins), so saving several times quickly doesn't
queue builds or race `ninja` on `build/`.

**Why it's fast (~0.6s, not ~3s).** A save runs `rom1 build
build/objdiff/base/<unit>.obj` — one `cl`, scoped to the edited unit — then
`objdiff-cli diff -u <unit>` against the **cached target objs**. It deliberately
**skips delink and the all-units `report.json`**, the two steps whose cost scales
with the project's unit count. That's sound because the **target side is fixed by
the retail EXE**: a body edit can't change it, and delink/report only matter when
you add/move/rename a *labeled* function. The overlay %s use
`function_reloc_diffs=none`, the same setting `report generate` uses, so they
match the report's `fuzzy_match_percent` exactly (no number jump).

**Tradeoff.** Between full builds, the **overall %** and **other units'** numbers
(the `vs` status view) stay at the last full build — only the edited unit updates
live. Run **`vB` / `:Rom1Build`** for the full pipeline (delink + all-units
report + overall %); that's also what picks up a **brand-new function** you just
added (and a save in a file with no `RVA(...)` yet falls back to a full build
automatically, to wire the new unit into the graph).

### Format on save (`:Rom1 autoformat`)

Off by default. When on, **saving a source file** under `src/` or `include/`
(`*.c`/`*.cpp`/`*.cc`/`*.cxx`/`*.h`/`*.hpp`/`*.hh`) runs `clang-format` on **just
that file** in place before it hits disk — the same root `.clang-format` (and so
the same whitespace-only, matching-neutral result) as the tree-wide `rom1
format`, but scoped to the file you're editing. It's a no-op on already-formatted
files (the buffer and its undo history are left untouched), skips `vendor/` and
anything outside `src/`/`include/`, and preserves your cursor/scroll. Enable per
session with `:Rom1 autoformat`, or by default with `format_on_save = true` in
`setup`. Needs `clang-format` on `PATH` (the dev shell provides it).

The `autobuild`, `autoformat`, and `hints` toggles are **remembered per checkout**
in `build/rom1-nvim.json` (gitignored), so each worktree keeps its own setting
across restarts; a remembered toggle wins over the `setup` default.

## Requirements

`objdiff-cli` on `PATH` — launch nvim from the project dev shell (`nix
develop`). A populated `build/` (run `rom1 build` once if it's a fresh
checkout). The build command needs the dev shell's toolchain env, which it
enters itself when nvim was launched outside the shell.

## Install

**You usually don't have to.** The project dev shell wraps `nvim` so it
auto-loads this plugin — when you `nix develop` (either shell) you'll see:

```
[rom1] nvim       : WRAPPED -> nvim now auto-loads editor/nvim (...)
```

The wrap is a small script on `PATH` that execs your own nvim with
`--cmd "set rtp^=…/editor/nvim"` (so your config and plugins are untouched, and
plain `nvim` outside the shell is unchanged). Defined in `flake.nix`
(`nvimShimHook`).

To load it **everywhere** (outside the dev shell too), add it to your plugin
manager instead — e.g. lazy.nvim, pointing at this in-repo directory:

```lua
{ dir = "~/Projects/rom1/editor/nvim", ft = { "c", "cpp" } }
```

Optional config (defaults shown):

```lua
require("rom1").setup({
  keymaps = true,            -- set false to bind your own
  hints = true,              -- inline match-% after each RVA(...)
  build_on_save = false,     -- rebuild quietly on every TU save
  format_on_save = false,    -- clang-format the saved file (src/ + include/)
  split = "botright vsplit", -- where asm/status views open
})
```

Outside a rom1 checkout (no `config/units.toml` above the buffer) the plugin
stays inert.
