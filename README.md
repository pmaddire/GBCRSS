# GraphCode Intelligence Engine (GCIE)

GCIE is a graph-first code intelligence engine that minimizes LLM prompt context.

It is designed for coding-agent workflows where we want to retrieve the smallest
useful set of code and operational context instead of reading whole files or
whole directories into the model.

## How It Works

GCIE builds a retrieval-oriented view of a repository and then composes context
from several signals:

1. Repository scan
   - discovers source files, frontend files, config files, and selected docs
2. Graph and index construction
   - structure and relationship data
   - semantic search index
   - architecture-oriented metadata where available
3. Multi-channel retrieval
   - lexical filename/path/content matching
   - semantic vector matching
   - query expansion for code and system terms
   - adjacency/support-file recovery
4. Fusion and reranking
   - merges candidates with stable deterministic ordering
   - boosts exact file mentions, wiring files, and intent-relevant code
5. Context packing
   - returns compact snippets or file-level context depending on the task
   - preserves important support files when confidence would otherwise be weak
6. Fallback
   - if the optimized path looks insufficient, GCIE can recover extra files via
     a broader fallback search instead of silently returning thin context

The practical goal is simple: return the implementation file, the wiring file,
and the nearest supporting files that explain behavior, while avoiding the token
cost of sending full repo surfaces to the model.

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

## Core Commands

- `gcie index <path>`
- `gcie query <file.py> "<question>"`
- `gcie debug <file.py> "<question>"`
- `gcie context <repo|file> "<task>" --budget auto --intent <edit|debug|refactor|explore> --mode basic`
- `gcie context-slices <repo> "<task>" --intent <edit|debug|refactor|explore> [--profile recall|low] [--stage-a 400] [--stage-b 800] [--max-total 1200] [--pin frontend/src/App.jsx] [--pin-budget 300] [--include-tests]`

## How To Use It

### 1. Index the repo

```
gcie index .
```

Re-run indexing after major structural changes.

### 2. Start with plain `context`

```
gcie context . "<task>" --budget auto --intent <edit|debug|refactor|explore>
```

Recommended intent guidance:

- `edit`: making code changes
- `debug`: tracing a bug or incorrect behavior
- `refactor`: changing structure or interfaces
- `explore`: understanding code without immediate edits

### 3. For cross-layer or wiring-heavy tasks, prefer a file-first query

This works better than abstract phrasing:

```
gcie context . "frontend/src/App.jsx selectedTheme activeJobId /api/convert/start app.py start_convert" --budget 1200 --intent edit
```

Good query ingredients:

- explicit file names
- endpoint names
- prop names
- function names
- config keys
- state variables

### 4. Use `context-slices` when you want the recall-first workflow

```
gcie context-slices . "<task>" --intent <edit|debug|refactor|explore>
```

Optional flags: `--profile low`, `--include-tests`, `--pin <path>`, `--max-total 1200`.

### 5. Verify before editing

GCIE should be treated as context compression, not final truth. For important
edits, verify the returned context with a targeted local search:

```
rg -n "<key symbols>" app.py main.py frontend/src/App.jsx
```

## Usage Patterns That Work Best

### Simple local tasks

Use:

```
gcie context . "<task>" --budget auto --intent debug
```

### Cross-layer frontend/backend tasks

Use:

```
gcie context . "<file-first symbol-rich query>" --budget 1200 --intent edit
```

Why:

- the extra budget improves recall for wiring files
- file-first phrasing reduces generic entrypoint noise

### High-recall workflows

Use:

```
gcie context-slices . "<task>" --intent edit --pin <expected wiring file>
```

This is still the safest mode when you already know a few must-have files.

## Agent Workflow

For coding agents, the safest practical pattern is:

1. Run GCIE first
2. Check that the result includes:
   - the main implementation file
   - the wiring or entry file
   - at least one validation or test surface when relevant
3. If a must-have file is missing:
   - rerun with a more file-first query
   - increase budget to `1000` or `1200`
   - or pin the missing file in `context-slices`
4. Verify with `rg` before editing

This usually gives a much better accuracy/token tradeoff than broad manual file
reading.

## Cache

Repo-wide context is cached to speed up repeated calls.

- `gcie cache-warm .`
- `gcie cache-status .`
- `gcie cache-clear .`

Cache file: `.gcie/cache/context_cache.json` (auto-invalidated on file changes).

## Frontend and Non-Python Files

Repo-wide context scans common frontend and config extensions and adds file nodes so
queries can retrieve non-Python surfaces when relevant.

Default extensions include: `.js`, `.jsx`, `.ts`, `.tsx`, `.css`, `.scss`, `.html`, `.vue`,
plus `.json`, `.yaml`, `.yml`, `.toml`, `.md`, `.txt`.

## Core Capabilities

- Repository scanning
- Graph construction (structure, call, variable, execution, git, test coverage)
- Symbolic + semantic + hybrid retrieval
- Bug localization
- Minimal LLM context building
- Architecture-aware context routing and fallback
- Agent-friendly retrieval for edit/debug/refactor workflows

## Publish For NPX

From this repo:

```powershell
npm login
npm publish --access public
```

Then users can run:

```powershell
npx -y @pmaddire/gcie@latest setup .
```

