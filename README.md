# GraphCode Intelligence Engine (GCIE)

GCIE is a graph-first code intelligence engine that minimizes LLM prompt context.

## Quick Start

1. Create venv: `.venv\\Scripts\\python.exe -m venv .venv`
2. Run tests: `.venv\\Scripts\\python.exe -m unittest`
3. CLI help: `.venv\\Scripts\\python.exe -m cli.app --help`

## NPM Wrapper

This repo includes a lightweight npm wrapper so you can run `gcie` like other npm CLIs.

1. Install dependencies for Python as usual.
2. Use one of these options:
   - Local: `npm install` then `npx gcie --help`
   - Global link: `npm link` then `gcie --help`

The wrapper automatically prefers `.venv` if present, and falls back to system Python.

## Core Capabilities

- Repository scanning
- Graph construction (structure, call, variable, execution, git, test coverage)
- Symbolic + semantic + hybrid retrieval
- Bug localization
- Minimal LLM context building