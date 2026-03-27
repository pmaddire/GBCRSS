# GCIE Setup In Any Repo

Use this file to onboard GCIE quickly in a new project.

## 0) One-Command Bootstrap

If GCIE is already installed locally:

```powershell
gcie.cmd setup .
```

NPX one-liner (after npm publish):

```powershell
npx gcie@latest
```

GitHub one-liner bootstrap (no prior setup required):

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/pmaddire/GBCRSS/main/scripts/bootstrap_from_github.ps1 | iex"
```

This initializes `.gcie` architecture tracking, writes portable workflow docs, and runs an initial index.


## 1) Install And Verify

```powershell
gcie.cmd --help
```

If this fails, use your local install method first (`npm link`, `npx`, or Python module invocation).

## 2) Index Once

```powershell
gcie.cmd index .
```

Re-run indexing after major structural changes.

## 3) Add Agent Workflow File

Copy `GCIE_USAGE.md` from GCIE into the target repo root.

## 4) Start With Portable Defaults

```powershell
gcie.cmd context . "<task>" --intent <edit|debug|refactor|explore> --budget auto
```

Then apply the adaptive loop in `GCIE_USAGE.md` if must-have coverage is incomplete.

## 5) Use Adaptive Mode Routing

- default: `plain-context-first`
- selective: `slicer-first` only for families where it benchmarks better
- always available: `direct-file-check` (`rg`) for verification/gap closure

## 6) Must-Have Gate Before Edits

Treat context as sufficient only when you have:
- implementation file(s)
- wiring/orchestration file(s)
- validation surface when risk is non-trivial

If missing, run targeted gap-fill for only the missing file.

## 7) Agent Prompt (Drop-In)

```text
Use GCIE as the primary context compressor.
Start with plain-context-first using file-first, symbol-heavy queries.
If must-have coverage is incomplete, adapt in this order:
1) improve query symbols/file anchors
2) adjust scope (subtree vs root)
3) raise budget one rung
4) targeted gap-fill for missing file(s)
5) decompose multi-hop chain only if still incomplete
Use slicer-first only for task families where it is benchmarked better.
Always verify with direct-file-check before edits when coverage is uncertain.
Stop retrieval as soon as must-have coverage is complete.
```
