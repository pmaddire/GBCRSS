# GCIE Agent Usage (Portable Default)

This file is designed to be dropped into any repository and used immediately.

Trigger line for agent instructions:
`Use GCIE for context lookup before reading files or making edits. Follow GCIE_USAGE.md.`

## Goal

Retrieve the smallest useful context while preserving edit safety.

Priority order:
1. accuracy (must-have coverage)
2. full-hit reliability
3. token efficiency

## Quick Start (Any Repo)

1. Identify must-have context categories for the task:
- implementation file(s)
- wiring/orchestration file(s)
- validation surface when risk is non-trivial
- this may be a test, spec, schema, contract, migration, config, or CLI surface depending on the repo

2. Run one primary retrieval with a file-first, symbol-heavy query:
```powershell
gcie.cmd context <path> "<file-first symbol-heavy query>" --intent <edit|debug|refactor|explore> --budget <shape budget>
```

3. Check must-have coverage.

4. If one must-have file is missing, run targeted gap-fill for only that file.

5. Stop immediately when must-have coverage is complete.

## Retrieval Modes (Adaptive Router)

Use three modes and choose by task family:

1. `plain-context-first` (default for most tasks)
2. `slicer-first` (for hard routed architecture or multi-hop families)
3. `direct-file-check` (verification and fast gap closure)

Plain-context command:
```powershell
gcie.cmd context <path> "<query>" --intent <edit|debug|refactor|explore> --budget <shape budget>
```

Slicer-first command:
```powershell
gcie.cmd context-slices <path> "<query>" --intent <edit|debug|refactor|explore>
```

Direct-file-check command:
```powershell
rg -n "<symbol1|symbol2|symbol3>" <likely files or subtree>
```

Mode-switch rule:
- start with `plain-context-first` unless setup calibration proved another mode is better for that family
- use `slicer-first` only for families where routing/architecture slices repeatedly outperform plain context
- use `direct-file-check` whenever must-have coverage is uncertain or one file remains missing
- do not keep retrying the same mode indefinitely; switch after one weak result

Portable starter policy:
- default all families to `plain-context-first`
- after first 10-20 tasks, promote individual families to `slicer-first` only if benchmarked better
- keep a family on plain-context if slicer is more expensive with no accuracy gain

## Architecture Tracking (Portable, In-Repo)

To make slicer mode adapt as the repo changes, keep architecture tracking inside the repo where GCIE runs.

Track these files under `.gcie/`:
- `.gcie/architecture.md`
- `.gcie/architecture_index.json`
- `.gcie/context_config.json`

How to keep it adaptive:
1. Bootstrap from user docs once (read-only):
- `ARCHITECTURE.md`, `README.md`, `PROJECT.md`, `docs/architecture.md`, `docs/system_design.md`
2. Use `.gcie/architecture.md` as GCIE-owned working architecture map.
3. Refresh `.gcie/architecture.md` and `.gcie/architecture_index.json` when structural changes happen:
- new subsystem
- major module split/merge
- interface/boundary change
- dependency-direction change
- active work-area shift
4. Do not overwrite user-owned docs unless explicitly asked.

Architecture confidence rule:
- if architecture slice confidence is low or required mappings are stale/missing, fallback to plain `context` automatically
- record fallback reason in `.gcie/context_config.json` when bypassing slicer mode

## Portable Defaults (Task-Shape Based)

Use these as a starting point in new repos.

Primary pass budgets:
- `auto`: simple same-layer or strong single-file lookup
- `900`: same-family two-file lookup, frontend-local component lookup
- `1100`: backend/config pair, same-layer backend pair
- `1150`: cross-layer UI/API flow
- `1300-1400`: explicit multi-hop chain (3+ linked files)

Gap-fill budgets:
- missing general implementation/wiring file: `900`
- missing small orchestration or entry file: `500`

Scope rule:
- use the smallest path scope that still contains the expected files
- use repo root (`.`) only for true cross-layer or backend orchestration recovery
- if explicit targets cluster in one subtree, broad repo-root retrieval is often worse than subtree retrieval

## Query Construction (Portable)

Use this pattern:

`<file-a> <file-b> <function/component> <state-or-arg> <route/flag> <config-key>`

Guidelines:
- include explicit file paths when known
- include 2 to 6 distinctive symbols
- include a caller or entry anchor when the target is indirect
- avoid vague summaries and long laundry-list queries

## Adaptive Loop (When Retrieval Is Weak)

Treat retrieval as weak if any are true:
- missing implementation or wiring category
- generic entry/support files dominate
- only tiny snippets from the target file appear, with no useful implementation body
- expected cross-layer endpoint is missing

Adapt in this order, one change at a time:

1. Query upgrade:
- add explicit file paths
- add missing symbols such as functions, props, routes, flags, or keys
- add caller or entry anchor

2. Scope correction:
- noisy root results: move to subtree scope
- missing cross-layer or backend anchor: use a targeted root query for that file

3. Budget bump:
- raise one rung only, roughly `+100` to `+250`

4. Targeted gap-fill:
- fetch only the missing must-have file(s)

5. Decompose chain, only if needed:
- for 4+ hops, split into adjacent 2-3 file hops

## Safe Efficiency Mode

Use only after stable coverage is achieved.

Rules:
- do not lower primary budgets for known hard shapes
- for a single missing file, try `800` before `900` only if the first pass already found same-family context
- if `800` misses, immediately retry the stable default
- if any miss persists, revert that task family to stable settings

Note:
- `800` is an experimental efficiency step-down, not a portable default truth
- keep it only if it preserves full must-have coverage in the current repo

## Verification Rule

Always verify with a quick local symbol check before editing:

```powershell
rg -n "symbol1|symbol2|symbol3" <likely files>
```

GCIE is a context compressor, not the final truth gate.

If one required file is still missing after retrieval, do direct-file-check first, then run one targeted GCIE call only for that file.

## Portable Stop Rule

Stop retrieval when all must-have categories are covered:
- implementation
- wiring/orchestration
- validation surface, when risk justifies it

Do not continue increasing budgets after sufficiency is reached.

## First 5 Tasks Calibration (Minimal)

For a new repo, track these fields for the first 5 tasks:
- task shape
- primary budget
- gap-fill used (Y/N)
- must-have full-hit (Y/N)
- total tokens

If a miss pattern repeats 2+ times in one task family:
- add one local override for that family only
- keep all other families on portable defaults

Update necessity rule:
- explicit workflow updates are optional, not required for baseline operation
- if results are stable, keep using portable defaults without changes
- add or update a local override only when the same miss pattern repeats 2-3 times

## Optional Appendix: Repo-Specific Overrides (Example)

These are examples from one mixed-layer repo and are not universal defaults.

1. `cross_layer_ui_api` override:
```powershell
gcie.cmd context frontend "src/App.jsx src/main.jsx <symbols>" --intent edit --budget 900
gcie.cmd context . "app.py start_convert selected_theme selectedTheme no_ai" --intent edit --budget 900
```

2. Stage 3/4 planner-builder pair override (`Plan_slides.py` + `Build_pptx.py`):
```powershell
gcie.cmd context . "Plan_slides.py content_slides section_divider figure_slides table_slide" --intent <intent> --budget 900
gcie.cmd context . "Build_pptx.py build_pptx render_eq_png apply_theme THEME_CHOICES" --intent <intent> --budget 900
```

3. Stage 1/2 with `main.py` override:
```powershell
gcie.cmd context . "Analyze_pdf_structure.py Extract_pdf_content.py extract_pages split_into_sections extract_images enrich_with_ai" --intent explore --budget 1100
gcie.cmd context . "main.py Stage 1 Stage 2 extract_pages enrich_with_ai" --intent explore --budget 500
```

4. Guardrail example:
- keep the stable workflow for families that regress under split retrieval
- example: `llm_client.py + Analyze_pdf_structure.py + Extract_pdf_content.py` in one benchmarked repo

If this appendix does not match your repo, ignore it and use only the portable sections above.
