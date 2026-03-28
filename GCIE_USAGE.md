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

## Generalization Contract (Required)

All workflow changes must be portable across repos.

Rules:
1. No hardcoded file-name rules in core workflow logic.
2. Prefer task-shape and evidence-based routing over repo-specific assumptions.
3. Keep repo-specific overrides optional, localized, and easy to remove.
4. Promote a rule only after repeated evidence (recommended: 2-3 consistent misses in one family).
5. Revert any change that improves tokens but reduces must-have hit rate.
6. Keep adaptation state in `.gcie/retrieval_profile.json`; do not require manual markdown tuning for normal operation.
7. Treat `GCIE_USAGE.md` defaults as the baseline contract for all repos; append local overrides only when justified by measured data.

## Quick Start (Any Repo)

1. Identify must-have context categories for the task:
- implementation file(s)
- wiring/orchestration file(s)
- validation surface when risk is non-trivial
- this may be a test, spec, schema, contract, migration, config, or CLI surface depending on the repo

2. Run one primary retrieval with a file-first, symbol-heavy query:
```powershell
gcie.cmd context <path> "<file-first symbol-heavy query>" --intent <edit|debug|refactor|explore> --budget <shape budget> --mode basic
```

Use `--mode adaptive` only when basic mode misses must-have coverage.

3. Check must-have coverage.

4. If one must-have file is missing, run targeted gap-fill for only that file.

5. Stop immediately when must-have coverage is complete.

## Retrieval Modes (Adaptive Router)

Use three modes and choose by task family:

1. `slicer-first` (default bootstrap mode per repo)
2. `plain-context-first` (fallback for families where slicer underperforms)
3. `direct-file-check` (verification and fast gap closure)

Plain-context command:
```powershell
gcie.cmd context <path> "<query>" --intent <edit|debug|refactor|explore> --budget <shape budget>
```

Slicer-first command:
Adaptive learning command (recommended when using slices):
```powershell
gcie.cmd context-slices . "<query>" --intent <edit|debug|refactor|explore> --profile adaptive
```
```powershell
gcie.cmd context-slices <path> "<query>" --intent <edit|debug|refactor|explore>
```

Direct-file-check command:
```powershell
rg -n "<symbol1|symbol2|symbol3>" <likely files or subtree>
```

Mode-switch rule:
- start with `slicer-first` while bootstrapping a repo
- if must-have coverage is incomplete after one slicer pass, retry with `plain-context-first` for that task
- if a task family misses with slicer 2+ times during calibration, mark that family as `plain-context-first` by default
- keep slicer on families where it repeatedly meets must-have coverage with lower or comparable tokens
- use `direct-file-check` whenever must-have coverage is uncertain or one file remains missing
- do not keep retrying the same mode indefinitely; switch after one weak result

Portable starter policy:
- default all families to `slicer-first` for the first calibration window
- after first 10-20 tasks, persist per-family defaults based on observed hit rate and token cost
- demote any family to plain-context if slicer is less accurate or more expensive without quality gains

## Architecture Tracking (Portable, In-Repo)

To make slicer mode adapt as the repo changes, keep architecture tracking inside the repo where GCIE runs.

Track these files under `.gcie/` (including adaptive learning state):
- `.gcie/architecture.md`
- `.gcie/architecture_index.json`
- `.gcie/context_config.json`
- `.gcie/retrieval_profile.json` (learned per-task-family slice/budget defaults)

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

## Portable Windows Path Safety Addendum

Use this addendum on Windows/PowerShell to avoid path tokenization issues with `(` `)` `[` `]`.

1. Always quote both scope and query:
```powershell
gcie.cmd context "src/app" "src/app/(portal)/user/requests/submit/page.tsx RequestSubmitPage review drawer" --intent explore --budget 900
```

2. In scripts, pass argument arrays instead of concatenated command strings:
```powershell
& gcie.cmd context 'src/app' 'src/app/(portal)/admin/schedule/page.tsx schedule edge-case panel' --intent explore --budget 900
```

3. For paths with `()`/`[]`, prefer subtree scope + exact path in query:
```powershell
gcie.cmd context "src/app" "src/app/(portal)/user/requests/submit/page.tsx RequestSubmitPage" --intent explore --budget 900
```

4. If still missing, run one safe recovery pass:
```powershell
gcie.cmd context "src/app" "<exact-file-path> <file-stem> <2-4 symbols>" --intent <intent> --budget 1100
```

## Adaptive Benchmark Addendum (Optional)

Use this section to let GCIE learn per-repo routing defaults (`slicer` vs `plain` vs baseline/manual).

Critical priority:
- `100% must-have hit rate` is required before any efficiency optimization.
- never trade recall for token savings.

### Trigger

If the user asks to run a GCIE benchmark (for example: `run GCIE benchmark`), start this process automatically.

Also run this process automatically after a fresh install + trigger line:
`Use GCIE for context lookup before reading files or making edits. Follow GCIE_USAGE.md.`

First-use trigger detection rule (required):
- treat the first matching trigger in a repo session as activation for automatic post-trigger adaptation
- accept equivalent trigger variants, including:
  - minor typos/case/punctuation differences of the trigger line
  - shorthand intent phrases like `use GCIE for context lookup` + `follow GCIE_USAGE`
  - explicit confirmations like `that was the trigger` or `run automatic post-trigger adaptation`
- only skip auto-start when the user explicitly opts out

### Pre-Calibration Readiness Gate (Required Before Accuracy Calibration)

Run this gate immediately after trigger detection and before any accuracy benchmarking.

1. `Index + Architecture Refresh`
- run index from repo root: `gcie.cmd index .`
- refresh `.gcie/architecture.md` and `.gcie/architecture_index.json` from current repo structure
- ensure benchmarking uses repo-root index only (`./.gcie/`)

2. `Readiness Probe`
- run a small stratified probe (`10-20` queries) using `context` and `context-slices`
- objective: verify must-have coverage is reachable with GCIE modes before full calibration

3. `Readiness Adaptation Loop` (required order)
- if must-have coverage is incomplete, adapt in this order:
  1) improve query symbols/file anchors
  2) adjust scope (subtree vs root)
  3) raise budget one rung
  4) targeted gap-fill for missing file(s)
  5) decompose multi-hop chain only if still incomplete

4. `Readiness Gate Decision`
- proceed to Accuracy Calibration only after readiness probe reaches stable must-have coverage
- if readiness still fails under budget cap, do not force GCIE routing defaults; keep safer fallback for affected families and continue tracking for recalibration

### Automatic Post-Trigger Adaptation (Required)

Immediately after receiving the trigger line in a freshly installed repo, run this protocol.
Use `5` workers by default for speed.

0. `Pre-Calibration Readiness Gate`
- run the readiness gate above
- do not enter calibration until readiness passes

1. `Mode + Slices Baseline Calibration`
- classify tasks into query families
- for each family, benchmark at least:
  - `plain-context-first`
  - `slicer-first` with `--profile adaptive`
- in slicer mode, calibrate these knobs in order:
  1) slice scope (repo root vs subtree)
  2) `stage_a` budget
  3) `stage_b` retry budget
  4) `max_total` packing cap
  5) `pin`/targeted gap-fill budget
  6) include-tests behavior (only when needed)
- objective: maximize must-have hit rate first, then minimize tokens

1A. `Query Adaptation Calibration` (required)
- evaluate at least 2-3 query variants per family before changing budgets:
  1) file-first + symbol-heavy
  2) caller/entry-anchored variant
  3) flow-anchored variant (route/flag/config/stage terms)
- score each variant by:
  - must-have hit rate
  - tokens-per-hit
  - stability across reruns
- keep the smallest query form that preserves `100%` must-have hit rate
- if a family is unstable, adapt query shape in this order:
  1) add explicit file path(s)
  2) add 2-6 distinctive symbols
  3) add caller/entry anchor
  4) add flow anchors (route, flag, config key, stage marker)
  5) remove vague/noisy terms
- persist winning query templates per family in `.gcie/retrieval_profile.json` metadata (or benchmark artifacts) and reuse them during calibration

2. `Slices Learning Loop` (required)
- run repeated `context-slices --profile adaptive` passes on the calibration set
- after each pass, review learned profile:
  - `gcie.cmd adaptive-profile .`
- confirm learning quality per family:
  - stable hit rate
  - stable preferred slice paths
  - stable stage budgets
- if learning drifts or over-expands slices:
  - clear and rerun with tighter caps:
    - `gcie.cmd adaptive-profile . --clear`

3. `Accuracy Lock`
- require `100%` must-have hit rate overall and per family
- run 2 consecutive verification passes
- if either pass drops below `100%`, return to calibration

4. `Efficiency Adaptation` (only after lock)
- run controlled efficiency sweeps per family
- run `5` default iterations (unless user overrides)
- before each iteration, snapshot current adaptive profile (`.gcie/retrieval_profile.json`)
- for slicer mode, step down one variable at a time:
  - lower `stage_a`
  - lower `max_total`
  - keep `stage_b` safety floor unless evidence supports reduction
- hard gate per iteration:
  - if hit rate drops below `100%`, restore snapshot immediately (rollback)
  - if no token gain for 2 consecutive iterations, stop early
- keep only changes that preserve `100%` hit rate
- prefer the lowest-token option per family under the hard accuracy gate

5. `Post-Efficiency Stress Validation`
- run one final `50` query validation benchmark on the selected workflow
- shard evenly across workers (recommended `10 + 10 + 10 + 10 + 10`)
- require:
  - combined hit rate `100%`
  - no regression versus locked config
- on failure, rollback to last known 100%-hit workflow

6. `Write-Back`
- write artifacts to `.planning/`
- persist adaptive learning state in `.gcie/retrieval_profile.json`
- update `.gcie/context_config.json` active defaults
- update `GCIE_USAGE.md` learned routing notes only when changes are stable

7. `Activate And Use`
- treat the resulting workflow as active for normal tasks
- use adaptive slices by default where they won calibration:
  - `gcie.cmd context-slices . "<query>" --intent <...> --profile adaptive`
- if a family regresses, fallback to plain context for that family and keep adaptation running in background
### Runtime Efficiency Mode (Reduce Adaptation Wall-Time)

Use a two-tier execution model so trigger runs are faster:

1. `Fast Tier` (default on trigger)
- benchmark size: `10-20` stratified queries
- run full accuracy lock + efficiency iterations on this smaller set
- if no meaningful gain, stop early and keep current workflow

2. `Full Tier` (promotion validation)
- run full `50` query stress validation only once at end-of-cycle when:
  - Fast Tier finds a better candidate, or
  - major refactor/change trigger fires, or
  - user explicitly requests `tier=full`

3. `Non-Blocking Behavior`
- Full Tier should run in background when possible
- keep user-facing workflow unblocked by continuing to use last-known-good config

### Continuous Adaptation Over Time (Background Recalibration)

Use this to keep GCIE tuned as the repo evolves.

Trigger background recalibration when any condition is true:
1. `Repo Change Trigger`
- significant code churn since last adaptation (recommended thresholds):
  - `>= 20` files changed, or
  - `>= 8` files changed in high-impact families (`src/app`, `src/lib`, `src/data`, `config/docs architecture`)

2. `Savings Decay Trigger`
- rolling token savings drops by `>= 10 percentage points` from the active workflow baseline over recent tasks

3. `Accuracy Risk Trigger`
- repeated must-have misses in the same family (`>= 2` misses in recent window)

### Continuous Adaptation Guardrails (Required)

To avoid wasting tokens or interrupting user flow:
1. `Primary Trigger Priority`
- trigger recalibration primarily from:
  - savings-decline signals, and
  - major repo-change signals (for example, large refactors)
- do not block adaptation just because a recent run happened if a major-change trigger is present

2. `Minimum Evidence Window`
- require enough recent activity before triggering (recommended: at least `20` retrieval events)

3. `Quiet-Time Scheduling`
- run only when no active user-critical action is in progress
- run as low-priority background work; never block the foreground task

4. `Token Budget Cap`
- set a per-run adaptation budget cap (recommended cap: equivalent of one `50` query cycle)
- if cap is reached, stop and keep current workflow

5. `Change Threshold Hysteresis`
- require trigger condition to persist across 2 checks before launching recalibration
- prevents flapping from short-term noise

6. `Periodic Accuracy Health Check`
- run a lightweight accuracy check on a small sampled set every few hours
- if accuracy drift is detected, escalate to full background recalibration

7. `Early-Stop Rule`
- during efficiency iterations, stop if no token improvement is observed for 2 consecutive iterations
- keep current best candidate and skip remaining iterations

8. `Family-Scoped Recalibration`
- if changes are localized, recalibrate affected families first
- escalate to full-family recalibration only if localized pass fails accuracy or savings thresholds

Background recalibration flow:
1. launch background sub-agent(s) to run `accuracy -> lock -> efficiency -> 50-query stress` on fresh random samples
2. do not interrupt the foreground user task; keep using current active workflow until background run finishes
3. if background run produces a strictly better workflow under `100%` hit gates, promote it
4. write updates to:
- `GCIE_USAGE.md` learned sections
- `.gcie/context_config.json`
- `.gcie/retrieval_profile.json` (learned per-task-family slice/budget defaults)
- adaptation ledger entry in this file
5. if background run fails any hard gate, discard candidate and keep current workflow

Default background execution profile:
- use `5` sub-agents for recalibration work
- keep accuracy lock and stress validation mandatory
- never auto-promote a workflow with hit rate below `100%`

### Index Selection Guard (Required)

Run benchmarks from repo root and use the repo-root GCIE index only:
- preferred index root: `./.gcie/`
- do not use nested indexes such as `./.planning/.gcie/` for benchmark calibration
- if nested `.gcie` folders exist, either remove them or explicitly avoid benchmarking from those directories

Reason:
- mixed index roots can corrupt family-level routing conclusions and produce unstable hit-rate results.

### Benchmark Command Template (Copy/Paste)

Use one of these prompts:

```text
run GCIE benchmark
```

```text
run GCIE benchmark benchmark_size=10
```

```text
run GCIE benchmark benchmark_size=25
```

```text
run GCIE benchmark benchmark_size=10 efficiency_iterations=6
```

```text
run GCIE benchmark tier=fast
```

```text
run GCIE benchmark tier=full benchmark_size=50 efficiency_iterations=5
```

Interpretation rules:
- if `benchmark_size` is omitted, use `10`
- if `benchmark_size` is invalid or too small, clamp to `10`
- if very large, cap at a practical upper bound (recommended `50`)
- if `efficiency_iterations` is omitted, use `5`
- user may request more with `efficiency_iterations=<N>`
- clamp invalid or too-small values to `5`
- recommended range: `5` to `12` (higher may find better configs but takes longer)
- if `tier` is omitted, use `fast`
- `tier=fast` recommended benchmark size: `10-20`
- `tier=full` recommended benchmark size: `50`

### Mandatory Bootstrap Calibration Sequence

Run this sequence in order:

1. `Recall Calibration Stage` (required)
- run benchmark with baseline defaults
- adapt retrieval mode/scope/budget per family until overall hit rate is `100%`
- if any family remains below `100%`, force that family to a safer default:
  - `plain-context-first` with higher stable budget, or
  - `baseline/manual` if GCIE modes are still insufficient

2. `Recall Lock Verification` (required)
- rerun benchmark at same size and distribution
- require `100%` hit rate in at least 2 consecutive runs before moving on

3. `Efficiency Stage` (optional, only after lock)
- run controlled budget/query reductions
- keep changes only if hit rate stays at `100%`
- if hit rate drops, rollback that change immediately
- only accept an efficiency profile if it also improves on `baseline_start` token metrics

4. `Activation Rule` (required)
- after efficiency stage, write the new best workflow into:
  - `GCIE_USAGE.md` learned sections
  - `.gcie/context_config.json`
- `.gcie/retrieval_profile.json` (learned per-task-family slice/budget defaults)
- immediately use that activated workflow for the 50-query stress test
- if stress test passes, keep it active for ongoing user work
- if stress test fails, rollback to previous last-known-good 100%-hit workflow

### Benchmark Size

- user may set `benchmark_size=<N>`
- default to `N=10` when not specified
- recommended range: `10` to `50`

### Query Set Construction

Generate a random, stratified query set from repo-relevant families.

Target families (balanced distribution):
1. single-file symbol lookup
2. multi-hop wiring/flow lookup
3. planning/docs lookup
4. config/env/flags lookup
5. route/page/component lookup (include paths with `()`/`[]` when present)
6. data/selector/service relationship lookup

Sampling rule:
- distribute queries as evenly as possible across families
- if `N` is not divisible evenly, assign remainder to highest-risk families:
  multi-hop, route/page, and config/env

### Modes To Compare

Run each query with:
1. `slicer-first`
2. `plain-context-first`
3. baseline/manual retrieval (normal retrieval without GCIE tool routing)

### Metrics

For each query and mode, record:
- must-have file hit (`true/false`)
- tokens used (or closest available token proxy)
- top retrieved files
- retrieval steps/escalations

Summary metrics by family and overall:
- hit rate
- token average
- token median
- tokens-per-hit (`total_tokens / hit_count`)

Starting baseline tracking (required):
- before any adaptive changes, store `baseline_start` for the current run:
  - mode defaults used at start
  - overall hit rate
  - total tokens
  - tokens-per-hit
- treat this as the anchor for all efficiency comparisons in that run
- report deltas against `baseline_start` after each adaptation step:
  - `hit_rate_delta`
  - `total_tokens_delta`
  - `tokens_per_hit_delta`

### Decision Rules (Learning)

Per family, choose default mode using:
1. highest hit rate
2. if tie, lowest tokens-per-hit
3. if still tie, lower median tokens

Demotion rules:
- if slicer miss-rate > 0% in recall-calibration, do not keep slicer as default for that family
- if both slicer and plain fail, route family to baseline/manual until re-index + recalibration
- during efficiency stage, any hit-rate regression immediately reverts to last known 100%-hit config

Promotion rules:
- in recall-calibration, promote only modes that achieve `100%` hit rate
- in efficiency stage, promote only if `100%` hit rate is preserved and tokens-per-hit improves vs current
- do not finalize efficiency changes unless they also improve vs `baseline_start`

### Persistence

Persist learned per-family defaults to `.gcie/context_config.json` (or equivalent local GCIE config), including:
- family name
- current default mode
- last benchmark date
- evaluation window size
- hit rate and token metrics

Also write learned routing rules into this `GCIE_USAGE.md` file under a dedicated section:
## Learned Routing Overrides (Repo-Local, Mutable)

No active learned overrides. Run adaptive calibration to populate this section.

## Post-Lock Efficiency Tuning Protocol (Accuracy-Preserved)

Run this section only after recall lock is proven (`100%` hit rate in 2 consecutive lock runs).

Primary rule:
- perfect hit rate is non-negotiable; efficiency tuning must never reduce coverage.

### Candidate Space (What To Tune)

Tune these levers in controlled, one-change-at-a-time steps:
1. mode by family:
- `slicer-first`
- `plain-context-first`
- `baseline-manual` (normal retrieval path without GCIE routing), only when it is both safe and cheaper

2. budget by family:
- lower one rung at a time (`auto -> 900 -> 850 -> 800 -> 750` where applicable)
- stop stepping down at first recall regression

3. query shape by family:
- compact file-first symbols
- caller-anchored query variant
- exact-file anchored variant

4. hybrid flow by family:
- `slicer -> plain gap-fill`
- `plain -> direct-file-check`
- `slicer -> direct-file-check -> exact-file context`

### Hard Acceptance Gate

A candidate configuration is accepted only if all are true:
1. overall hit rate remains `100%`
2. every family in scope remains `100%`
3. lock verification still passes (2 consecutive runs)
4. tokens improve vs current active config
5. tokens also improve vs `baseline_start` anchor

If any condition fails:
- revert immediately to last known 100%-hit config.

### Per-Family Selection Rule

For each family, choose defaults using this order:
1. `100%` hit requirement (mandatory)
2. lowest tokens-per-hit
3. lowest median tokens
4. lowest escalation count

If no GCIE mode can keep `100%` for a family:
- set that family to `baseline-manual` until next recalibration.

### Efficiency Tuning Sequence

Run in this exact sequence:
1. freeze current recall-locked config as `efficiency_start`
2. test mode alternatives per family (slicer/plain/baseline-manual)
3. test budget step-downs for winning mode per family
4. test query-shape variants for winning mode+budget
5. test hybrid fallback variants only where still expensive
6. run 2 lock-verification passes on resulting config
7. persist only if all acceptance gates pass

### SETUP_ANY_REPO Alignment

When adapting, keep this order from setup guidance:
1. improve query anchors/symbols
2. adjust scope (`subtree` before repo root)
3. raise or lower budget by one rung
4. targeted gap-fill for missing files
5. decompose multi-hop only when needed

Use `slicer-first` where it is benchmarked best; otherwise route family to plain or baseline-manual.

### Benchmark Trigger Behavior

When user requests:
- `run GCIE benchmark`

Default behavior:
1. run recall calibration to lock `100%`
2. run this efficiency protocol
3. report:
- locked recall metrics
- efficiency deltas vs `efficiency_start`
- efficiency deltas vs `baseline_start`
- final per-family routing defaults

If user asks for more efficiency iterations:
1. re-enter efficiency loop with requested `efficiency_iterations=<N>`
2. evaluate candidates under the same 100%-hit hard gate
3. update `GCIE_USAGE.md` learned workflow and `.gcie/context_config.json`
4. run required 50-query stress validation using that updated workflow
5. report results and keep that workflow active for all future GCIE usage















