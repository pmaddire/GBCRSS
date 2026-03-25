# GraphCode Intelligence Engine (GCIE)

GCIE is a graph-first code intelligence engine that minimizes LLM prompt context.

## Quick Start (local)

1. Create venv: `.venv\\Scripts\\python.exe -m venv .venv`
2. Install deps as needed (networkx, GitPython, typer):
   `.venv\\Scripts\\python.exe -m pip install networkx GitPython typer`
3. Run tests: `.venv\\Scripts\\python.exe -m unittest`
4. CLI help: `.venv\\Scripts\\python.exe -m cli.app --help`

## NPM Wrapper (recommended)

This repo includes a lightweight npm wrapper so you can run `gcie` like other npm CLIs.

1. In GCIE repo: `npm link`
2. In target repo: `gcie --help`

Local option:
- `npm install` then `npx gcie --help`

The wrapper prefers `.venv` in the GCIE repo and falls back to system Python.

## Core Commands

- `gcie index <path>`
- `gcie query <file.py> "<question>"`
- `gcie debug <file.py> "<question>"`
- `gcie context <repo|file> "<task>" --budget auto --intent <edit|debug|refactor|explore>`

## Agent Usage (context first)

```
gcie context . "<task>" --budget auto --intent <edit|debug|refactor|explore>
```

Use only the returned snippets as working context. If insufficient, increase budget or rerun.

## Cache

Repo-wide context is cached to speed up repeated calls.

- `gcie cache-warm .`
- `gcie cache-status .`
- `gcie cache-clear .`

Cache file: `.gcie/cache/context_cache.json` (auto-invalidated on file changes).

## Core Capabilities

- Repository scanning
- Graph construction (structure, call, variable, execution, git, test coverage)
- Symbolic + semantic + hybrid retrieval
- Bug localization
- Minimal LLM context building