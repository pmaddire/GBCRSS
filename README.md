# GraphCode Intelligence Engine (GCIE)

GCIE is a graph-first code intelligence engine that minimizes LLM prompt context.

## Quick Start

1. Create venv: `.venv\\Scripts\\python.exe -m venv .venv`
2. Install deps as needed (networkx, GitPython, typer):
   `.venv\\Scripts\\python.exe -m pip install networkx GitPython typer`
3. Run tests: `.venv\\Scripts\\python.exe -m unittest`
4. CLI help: `.venv\\Scripts\\python.exe -m cli.app --help`

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
   - `npm link gcie`
3. Verify:
   - `gcie --help`

### C) Windows note

If PowerShell blocks the shim, use `gcie.cmd` instead of `gcie`.

## NPM Wrapper

This repo includes a lightweight npm wrapper so you can run `gcie` like other npm CLIs.

1. In GCIE repo: `npm link`
2. In target repo: `gcie --help`

Local option:
- `npm install` then `npx gcie --help`

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

## Core Commands

- `gcie index <path>`
- `gcie query <file.py> "<question>"`
- `gcie debug <file.py> "<question>"`
- `gcie context <repo|file> "<task>" --budget auto --intent <edit|debug|refactor|explore>`
- `gcie context-slices <repo> "<task>" --intent <edit|debug|refactor|explore> [--profile recall|low] [--stage-a 400] [--stage-b 800] [--max-total 1200] [--pin frontend/src/App.jsx] [--pin-budget 300] [--include-tests]`

## Agent Usage (context first)

```
gcie context . "<task>" --budget auto --intent <edit|debug|refactor|explore>
```

For more reliable recall, use path-scoped slices with the default two-stage retrieval:

```
gcie context-slices . "<task>" --intent <edit|debug|refactor|explore>
```

Optional flags: `--profile low`, `--include-tests`, `--pin <path>`, `--max-total 1200`.

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
