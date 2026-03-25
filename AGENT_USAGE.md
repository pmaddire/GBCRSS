# GCIE Agent Usage Guide

This guide explains how any AI coding agent should use GCIE to reduce context size while preserving accuracy.

## 1) Baseline Rule

Before making any code change, run:

```
gcie context-slices . "<task>" --intent <edit|debug|refactor|explore>
```

Use only the returned snippets as working context. If insufficient, add a pin or increase budgets.

## 2) Profiles

- `--profile recall` (default): higher recall, still strong savings.
- `--profile low`: aggressive budgets, cheaper but can miss files.

Defaults:
- recall: stage-a 400, stage-b 800, max-total 1200, pin-budget 300
- low: stage-a 300, stage-b 600, max-total 800, pin-budget 200

## 3) Skip Tests Unless Needed

Only include tests when you are writing/updating tests or touching risky logic:

```
--include-tests
```

## 4) File Pinning for Wiring

If a required wiring file is missing (commonly `frontend/src/App.jsx`), pin it directly:

```
gcie context-slices . "<task wiring keywords>" --pin frontend/src/App.jsx --pin-budget 300 --intent edit
```

## 5) Token Gate

Default max output is `--max-total 1200` tokens for medium tasks.
If required files are still missing, GCIE can exceed this cap to surface more context.

## 6) Query Phrasing

Use explicit nouns from code, not abstract summaries:

- Better: "api export endpoint doc_type session_id markdown"
- Better: "Canvas.test.jsx and Canvas.jsx for no architecture nodes generated"
- Better: "refinement rename subsystem patch persisted session outputs"

Include filenames or function/prop names where possible.

## 7) Cache Workflow

```
gcie cache-warm .
gcie cache-status .
gcie cache-clear .
```

Cache is stored at `.gcie/cache/context_cache.json` and auto-invalidates on file changes.

## 8) Sufficiency Gate (required before edits)

Context is sufficient only when results include all of:

- Primary implementation file(s)
- Wiring/handler file(s)
- At least one relevant test file (only when `--include-tests` is used)

If any are missing, add pins and/or raise budgets before editing.

## 9) Notes

- `gcie context-slices` works for repo paths and uses path-scoped slices by default.
- In Windows shells, `gcie.cmd` may be more reliable than `gcie`.
- If `gcie query/debug` fails for repo root, use `gcie context-slices` instead.
