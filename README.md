# GraphCode Intelligence Engine (GCIE)

GCIE is a graph-first code intelligence engine that minimizes LLM prompt context.

It is designed for coding-agent workflows where we want to retrieve the smallest
useful set of code and operational context instead of reading whole files or
whole directories into the model.

## How It Works

GCIE is an adaptive context retrieval engine for coding agents.

At a high level:

1. Index + architecture snapshot
   - `gcie index .` scans the repo and builds retrieval artifacts under `.gcie/`.
   - GCIE tracks architecture/retrieval state so it can route future queries better.

2. Query classification
   - `gcie context` classifies each request by intent and structure (single-file, same-layer pair, cross-layer, multi-hop).

3. Retrieval routing
   - GCIE chooses retrieval strategy (`plain`, `plain_gapfill`, `plain_chain`, or slices where useful), path scope, and token budget.
   - `--budget auto` uses built-in heuristics; explicit budgets are available when needed.

4. Gap-fill + must-have recovery
   - If expected support files are missing, GCIE runs targeted follow-up retrieval to recover must-have files instead of over-fetching whole repo context.

5. Adaptation loop (optional but recommended)
   - `gcie adapt .` benchmarks repo-local cases, selects per-family methods, and runs efficiency trials under an accuracy gate.
   - Results are written to `.planning/post_init_adaptation_report.json` and `.gcie/context_config.json`.

6. Fast path for day-to-day use
   - After adaptation, most tasks should run through `gcie context` with small prompt footprints and high recall.

The practical goal is to keep must-have coverage while minimizing token cost.
## Quick Start

1. Create venv: `.venv\\Scripts\\python.exe -m venv .venv`
2. Install deps as needed (networkx, GitPython, typer):
   `.venv\\Scripts\\python.exe -m pip install networkx GitPython typer`
3. Run tests: `.venv\\Scripts\\python.exe -m unittest`
4. CLI help: `.venv\\Scripts\\python.exe -m cli.app --help`

## Easiest Setup In Any Repo

Use this when you want a fast drop-in setup for coding agents.

1. Install GCIE CLI in the target repo (via your preferred method: npm link, local wrapper, or direct Python module).
2. Copy [GCIE_USAGE.md](c:\GBCRSS\GCIE_USAGE.md) into the target repo root.
3. Run one index pass:
   - `gcie.cmd index .`
4. Start using adaptive retrieval immediately:
   - `gcie.cmd context . "<task>" --intent edit --budget auto`

No heavy upfront tuning is required. The workflow starts portable-first and only adds local overrides after repeated miss patterns.

One-command repo bootstrap:
- `npx -y @pmaddire/gcie@latest setup .`

This creates `.gcie` architecture tracking files, copies portable agent workflow docs, and runs an initial index pass.

## Canonical Retrieval Protocol (2026-03)

Default protocol is now adaptive by task family:

1. `plain-context-first` for most tasks
2. `slicer-first` only where architecture/routed multi-hop families benchmark better
3. `direct-file-check` (`rg`) whenever must-have coverage is uncertain

Key rule: one mode does not fit all families. Mode routing is part of retrieval quality.

## Latest Protocol Benchmark Snapshot

Current protocol performance target: `78.9%` average token savings while preserving high accuracy.

From external 50-query mixed-layer benchmark results you provided:

- Stable plain-context baseline:
  - `1501.3` avg tokens
  - `78.6%` savings
  - `100%` accuracy
  - `100%` full-hit
- Naive slicer-first:
  - `1979.9` avg tokens
  - `72.4%` savings
  - `100%` accuracy
  - `100%` full-hit
- Adapted family-routed protocol:
  - `1372.3` avg tokens
  - `79.5%` savings
  - `100%` accuracy
  - `100%` full-hit

Net: adapted protocol preserved full accuracy while reducing average tokens by ~`129` vs stable baseline.

## NPX One-Liner

After publishing to npm, users can set up any repo with one command:

```powershell
npx -y @pmaddire/gcie@latest setup .
```

This runs `gcie setup .` in the current repo by default.
If Python deps are missing, GCIE now bootstraps a local package venv and installs required runtime dependencies automatically on first run.

Optional setup flags are passed through:

```powershell
npx -y @pmaddire/gcie@latest setup . --no-index
npx -y @pmaddire/gcie@latest setup . --force
```

For command-only usage without setup:

```powershell
npx -y @pmaddire/gcie@latest --help
```

## Agent Integration

To make your coding agent use GCIE automatically, add this trigger line to your
agent instructions (system prompt / repo instruction file):

`Use GCIE for context lookup before reading files or making edits. Follow GCIE_USAGE.md.`

Required file:
- keep `GCIE_USAGE.md` in the target repo root

Recommended setup:
1. Run one-command setup:
   - `npx -y @pmaddire/gcie@latest setup .`
2. Add the trigger line above to your agent instruction file.
3. Start normal coding tasks; the agent should use GCIE-first retrieval workflow.

## One-Command GitHub Bootstrap

Run this from the target repo to download GCIE from GitHub and set it up automatically:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/pmaddire/GBCRSS/main/scripts/bootstrap_from_github.ps1 | iex"
```

What it does:
- clones `https://github.com/pmaddire/GBCRSS.git`
- creates a temporary GCIE venv
- installs minimal deps
- runs `gcie setup` against your current repo

## In-Depth Setup

### A) Use GCIE directly from this repo

1. Create venv:
   - `python -m venv .venv`
2. Install deps:
   - `.venv\\Scripts\\python.exe -m pip install -r requirements.txt`
   - If `requirements.txt` is missing, install minimal deps:
     - `.venv\\Scripts\\python.exe -m pip install networkx GitPython typer`
3. Run the CLI:
   - `.venv\\Scripts\\python.exe -m cli.app --help`

### B) Use GCIE from another repo via npm link

1. In the GCIE repo:
   - `npm link`
2. In your target repo:
   - `npm link @pmaddire/gcie`
3. Verify:
   - `gcie --help`

### C) Windows note

If PowerShell blocks the shim, use `gcie.cmd` instead of `gcie`.

## NPM Wrapper

This repo includes a lightweight npm wrapper so you can run `gcie` like other npm CLIs.

1. In GCIE repo: `npm link`
2. In target repo: `gcie --help`

Local option:
- `npm install` then `npx @pmaddire/gcie@latest --help`

The wrapper prefers `.venv` in the GCIE repo and falls back to system Python.

## Performance Snapshot (AEO benchmark)

Two profiles observed after the update:

High-recall profile (recommended):
- Total GCIE tokens: 5,871
- No-tool baseline: 23,543
- Savings: 75.1%
- Coverage: 5/5 required files for all 3 tasks

Low-token profile (aggressive):
- Total GCIE tokens: 2,709
- No-tool baseline: 23,543
- Savings: 88.5%
- Coverage: incomplete (missed key files)

Per-task high-recall results:
- export_ui: 1,934 vs 5,481 (64.7% saved)
- blank_canvas: 2,322 vs 13,730 (83.1% saved)
- refine_patch: 1,615 vs 4,332 (62.7% saved)

## Current Accuracy And Token Snapshot

### Mixed-layer external repo finding

In a separate active repo with frontend/backend/build wiring, the newer
repo-local `gcie context` workflow performed much better when used with:

- file-first, symbol-heavy queries
- `--budget 1200` for cross-layer tasks
- `rg` verification before edits

Observed savings there:

- Frontend/API task: about `89.5%`
- Theme/build task: about `91.9%`
- Backend/config task: about `78.2%`
- Average: about `86.5%`

Important note:

- `--budget auto` was too conservative for those cross-layer tasks
- `--budget 1200` consistently improved recall without needing broad manual reads
- `1500` added more noise without materially helping more than `1200`

## Command Reference

Use `gcie` or `gcie.cmd` on Windows.

### Setup / Lifecycle

- `gcie setup .`
- `gcie setup . --force`
- `gcie setup . --no-index`
- `gcie setup . --adapt --adapt-benchmark-size 25 --adapt-efficiency-iterations 8 --adapt-workers 6`
- `gcie remove .`
- `gcie remove . --remove-planning`
- `gcie remove . --keep-usage --keep-setup-doc`

### Index and Retrieval

- `gcie index .`
- `gcie context . "<task>" --intent edit --budget auto --mode adaptive`
- `gcie context . "<task>" --intent debug --budget 1200 --mode adaptive`
- `gcie context-slices . "<task>" --intent edit --profile recall`
- `gcie context-slices . "<task>" --intent edit --profile low --pin frontend/src/App.jsx --pin-budget 300`

### Adaptation and Profile State

- `gcie adapt . --benchmark-size 25 --efficiency-iterations 8 --adapt-workers 6`
- `gcie adapt . --benchmark-size 25 --efficiency-iterations 8 --adapt-workers 6 --clear-profile`
- `gcie adaptive-profile .`
- `gcie adaptive-profile . --clear`

### Utility Commands

- `gcie query <path> "<question>"`
- `gcie debug <path> "<question>"`
- `gcie cache-status .`
- `gcie cache-warm .`
- `gcie cache-clear .`

## Recommended Workflow

### 1) Bootstrap once per repo

```powershell
gcie setup . --adapt --adapt-benchmark-size 25 --adapt-efficiency-iterations 8 --adapt-workers 6
```

### 2) Day-to-day retrieval

```powershell
gcie context . "<task>" --intent edit --budget auto --mode adaptive
```

For cross-layer flows, use file-first symbol-rich queries and optionally pin budget:

```powershell
gcie context . "frontend/src/App.jsx selectedTheme /api/convert/start app.py start_convert" --intent edit --budget 1200 --mode adaptive
```

### 3) Verify before edits on critical changes

```powershell
rg -n "<symbol1>|<symbol2>|<symbol3>" .
```

### 4) Re-adapt only when needed

Use adaptation again after large refactors, architecture shifts, or repeated recall misses:

```powershell
gcie adapt . --benchmark-size 25 --efficiency-iterations 8 --adapt-workers 6
```

If adaptation quality drifts due stale profile state, reset first:

```powershell
gcie adaptive-profile . --clear
gcie adapt . --benchmark-size 25 --efficiency-iterations 8 --adapt-workers 6 --clear-profile
```

## Notes

- `requested_benchmark_size` can be higher than `benchmark_size` used when fewer unique repo-local benchmark cases are available.
- `status: accuracy_locked_but_cost_risky` can appear when the selected 100%-accuracy policy is compared against a cheaper but lower-accuracy baseline.
- Primary success criteria remain must-have coverage and pass rate; optimize cost after lock.
