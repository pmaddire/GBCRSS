# GCIE Agent Usage (Portable, Accuracy-First)

Trigger line for agent instructions:
`Use GCIE for context lookup before reading files or making edits. Follow GCIE_USAGE.md.`

## Goal

Retrieve the smallest useful context without sacrificing edit safety.

Priority order:
1. accuracy (must-have coverage)
2. full-hit reliability
3. token efficiency

## Core Rules

1. Do not trade recall for token savings.
2. Stop retrieval as soon as must-have categories are covered.
3. Adapt per task family, not per one-off query.
4. Keep defaults portable; keep repo-specific learning in `.gcie` state.

## Commands (Tool-Synced)

Primary retrieval:
```powershell
gcie.cmd context <path> "<query>" --intent <edit|debug|refactor|explore> --budget <auto|int> --mode <basic|adaptive>
```

Sliced retrieval:
```powershell
gcie.cmd context-slices <path> "<query>" --intent <edit|debug|refactor|explore> --profile <low|recall|adaptive>
```

Adaptive profile state:
```powershell
gcie.cmd adaptive-profile .
gcie.cmd adaptive-profile . --clear
```

Post-init adaptation pipeline:
- run from the target repo root (cd <repo> first); use . as scope
- adaptation now bootstraps per-family method defaults before accuracy rounds (plain/plain-gapfill/plain-rescue/slices)
- adaptation case generation is mixed by design (single-file, same-layer pairs, cross-subtree pairs, and some 3-file chains on larger runs)
```powershell
gcie.cmd adapt . --benchmark-size 10 --efficiency-iterations 5 --clear-profile
# mixed-layer repos: use wider calibration
gcie.cmd adapt . --benchmark-size 25 --efficiency-iterations 5 --clear-profile
```

One-shot setup + adaptation:
```powershell
gcie.cmd setup . --adapt --adapt-benchmark-size 10 --adapt-efficiency-iterations 5
```

Setup and index:
```powershell
gcie.cmd setup .
gcie.cmd index .
```

Direct verification:
```powershell
rg -n "symbol1|symbol2|symbol3" <likely files or subtree>
```

## Must-Have Coverage Gate (Required)

Context is sufficient only when all needed categories are present:
- implementation file(s)
- wiring/orchestration/caller file(s)
- validation surface when risk is non-trivial (test/spec/schema/config/contract/CLI surface)

If any must-have file is missing, retrieval is incomplete.

If a must-have file appears only as compact/skeleton context, re-query that file explicitly (pin or targeted query) before editing.

Note: tests/spec files are often excluded by default. Add `--include-tests` only when test context is required.

## Query Construction (Portable, High-Signal)

Preferred pattern:
`<file-a> <file-b> <function/component> <route/flag> <state/config-key>`

Rules:
1. Use file-first, symbol-heavy phrasing.
2. Include explicit file paths when known.
3. Include 2-6 distinctive symbols.
4. Add caller/entry anchor when target is indirect.
5. Avoid natural-language question phrasing.

Example:
- Bad: `How does architecture routing decide when to fall back?`
- Good: `context/context_router.py context/fallback_evaluator.py architecture routing fallback confidence`

## Retrieval Modes (Adaptive Router)

Use three modes and route by observed outcomes:

1. `slicer-first`
2. `plain-context-first`
3. `direct-file-check`

Slicer-first:
```powershell
gcie.cmd context-slices <path> "<query>" --profile low --intent <intent>
```

Plain-context-first:
```powershell
gcie.cmd context <path> "<query>" --mode basic --intent <intent> --budget auto
```

Direct-file-check:
```powershell
rg -n "<symbols>" <files-or-subtree>
```

Routing policy:
1. Start new repos in `slicer-first` bootstrap mode.
2. If must-have coverage is incomplete after one slicer pass, switch that task to `plain-context-first`.
3. If a task family misses with slicer 2+ times in calibration, set that family default to `plain-context-first`.
4. Keep slicer for families where it is both accurate and cheaper.
5. If two GCIE attempts still miss required files, use `direct-file-check` and mark family `manual-verify-required` until recalibrated.

## Scope and Budget Baseline (Portable)

Scope rule:
1. Use the smallest path scope that still contains expected files.
2. Use repo root `.` only for true cross-layer recovery.
3. If explicit targets cluster in one subtree, subtree scope is usually better than root.

Profile ladder (concrete, portable):
1. `context-slices --profile low`
2. if miss: `context-slices --profile recall`
3. if miss: `context-slices --profile recall --pin <missing-file>`
4. if miss: `rg` direct check and targeted file retrieval

Plain-context budget baseline:
- `auto`: simple same-layer or strong single-file lookup
- `900`: same-family two-file lookup
- `1100`: backend/config pair or same-layer backend pair
- `1150`: cross-layer UI/API flow
- `1300-1400`: explicit multi-hop chain

Gap-fill baseline:
- general implementation/wiring file: `900`
- small entry/orchestrator file: `500`

## Adaptive Recovery Order (One Change At A Time)

When retrieval is weak, apply in this exact order:

1. Query upgrade: add explicit files, symbols, caller/entry anchor
2. Scope correction: subtree vs root
3. One profile/budget escalation
4. Targeted gap-fill for only missing must-have file(s), preferring direct file-path scope first
5. Multi-hop decomposition only if still incomplete

Stop condition:
- If a required file is still missing after two GCIE attempts (with query+scope corrected), stop GCIE retries and use `rg`.

## Architecture Tracking (Portable, In-Repo)

Track these under `.gcie/`:
- `.gcie/architecture.md`
- `.gcie/architecture_index.json`
- `.gcie/context_config.json`

Keep adaptive:
1. Bootstrap from user docs once (`ARCHITECTURE.md`, `README.md`, `PROJECT.md`, `docs/*architecture*`).
2. Treat `.gcie/architecture.md` as GCIE-owned working map.
3. Refresh architecture files when boundaries/subsystems/interfaces change.
4. Do not overwrite user-owned docs unless explicitly asked.

Fallback confidence rule:
- If architecture confidence is low or mappings are stale/missing, fallback to plain context and record reason in `.gcie/context_config.json`.

## Pre-Calibration Readiness Gate (Required)

Run before full adaptation:

1. Index + architecture refresh:
```powershell
gcie.cmd index .
```

2. Readiness probe:
- Run 10-20 stratified queries across major families using `context-slices` and `context`.

3. Readiness adaptation loop:
- Apply recovery order (query -> scope -> escalation -> targeted gap-fill -> decomposition).

4. Gate decision:
- Proceed to calibration only after coverage is reachable with stable behavior.
- If not reachable, keep safer fallback mode for affected families and continue tracking.

## Calibration Quality Gate (Cross-Repo, Required)

Before accepting adaptation results, verify calibration quality:

1. Family diversity floor:
- the generated benchmark set should cover at least 3 task families when the repo has multiple top-level subsystems
- if adaptation output is dominated by only `single_file` and `same_layer_pair`, treat it as underfit

2. Underfit recovery:
- rerun adaptation with wider calibration
```powershell
gcie.cmd adapt . --benchmark-size 25 --efficiency-iterations 5 --clear-profile
```
- keep `benchmark-size 10` only for small/single-layer repos or quick smoke checks

3. Accuracy-first acceptance:
- do not accept a profile below `100%` full-hit if a recoverable path exists
- run one rescue cycle (query upgrade -> scope correction -> one budget/profile rung -> targeted gap-fill)
- only then finalize family defaults

4. Cost lock sanity:
- if selected profile is much more expensive than cheapest (`>40%` token delta), keep status as cost-risk and continue family-level refinement
- do not freeze expensive global defaults unless they are uniquely required for `100%`
## Automatic Post-Trigger Adaptation (Required)

After trigger detection in a repo session:

1. `checkpoint: trigger_detected`
2. Run `gcie.cmd index .` -> `checkpoint: index_complete`
3. Run readiness probe -> `checkpoint: readiness_probe_complete`
4. Run accuracy calibration to 100% must-have hit -> `checkpoint: accuracy_lock_complete`
5. Run efficiency iterations only under hard accuracy gate -> `checkpoint: efficiency_complete`
6. Run final stress validation (recommended 50-query) -> `checkpoint: stress_validation_complete`
7. Write back results (`.planning`, `.gcie/context_config.json`, learned overrides section) -> `checkpoint: write_back_complete`

If any checkpoint fails, mark run `incomplete`, record failure artifact in `.planning/`, and continue recovery/fallback flow.

## Mandatory Bootstrap Calibration Sequence

1. Recall calibration stage (required):
- Tune mode/scope/query/profile until overall and per-family hit rates are 100%.

2. Recall lock verification (required):
- Require 2 consecutive 100% lock runs.

3. Efficiency stage (optional, only after lock):
- Test controlled reductions one change at a time.
- Immediately rollback any hit-rate regression.

4. Activation rule (required):
- Activate only if lock/stress pass.
- If stress fails, rollback to last known 100%-hit config.

## Metrics and Decision Rules

Per query, record:
- must-have hit (true/false)
- tokens used
- retrieved files
- escalations performed

Track overall and by family:
- hit rate
- average and median tokens
- tokens-per-hit (`total_tokens / hit_count`)

Selection rule per family:
1. highest hit rate
2. if tie: lowest tokens-per-hit
3. if tie: lowest median tokens

Demotion rules:
- If slicer miss-rate > 0% during recall calibration, do not keep slicer as default for that family.
- If both slicer and plain fail, route family to manual-verify until recalibration.

Promotion rules:
- Promote only configurations that preserve 100% hit.
- Efficiency changes must improve tokens without reducing hit rate.

## Continuous Adaptation Over Time

Trigger recalibration when any are true:
1. major repo-change signal (large refactor/churn)
2. savings decay (rolling savings drops materially vs active baseline)
3. repeated family misses (2+ in recent window)

Guardrails:
1. Use a minimum evidence window (recommended: 20 retrieval events).
2. Run in quiet/background mode when possible.
3. Cap adaptation budget per cycle.
4. Early-stop efficiency loop after 2 non-improving iterations.
5. Prefer family-scoped recalibration before full recalibration.

## Persistence

Persist learned defaults in `.gcie/context_config.json` and `.gcie/retrieval_profile.json` with:
- family
- default mode/profile
- last benchmark date
- hit/token metrics

Write repo-local learned routing here:

## Learned Routing Overrides (Repo-Local, Mutable)

No active learned overrides yet.
Populate after first full adaptation cycle.

## Agent Instructions Snippet (Copy/Paste)

```text
Use GCIE for context lookup before reading files or making edits. Follow GCIE_USAGE.md.
Prioritize must-have coverage over token savings.
Start with context-slices --profile low, then adapt using recovery order:
query -> scope -> profile/budget escalation -> targeted gap-fill -> rg fallback.
```

## Notes

1. This file is intentionally generalized and adaptive for any repo.
2. Keep repo-specific tuning in learned overrides and `.gcie` state, not in global defaults.
3. If in doubt, choose the higher-accuracy path first, then optimize tokens after lock.

## Cross-Repo Adaptation Rules (Required)

Use these rules to keep adaptation portable across repositories.

1. Adaptation case source must be repo-local:
- Prefer generated cases from actual files in the target repo.
- Do not rely on hardcoded expected files from another codebase family.
- If report `case_source` is not repo-local, treat the run as invalid.

2. Accuracy lock is required, but selection must be cost-aware:
- First gate: `100%` must-have full-hit.
- If multiple candidates pass `100%`, choose the lowest `tokens_per_expected_hit`.
- Do not keep `slices` as active default when a `plain` candidate also has `100%` and is cheaper.

3. Near-miss rescue before expensive lock-in:
- If a cheaper candidate is below lock by one file/family (for example `90%`), run a short rescue cycle before accepting an expensive `100%` candidate:
  1) targeted gap-fill for missing must-have file(s)
  2) scope correction (subtree if clustered)
  3) one budget rung increase
- Re-evaluate after rescue; prefer the cheaper candidate if it reaches `100%`.

4. Cost sanity guardrail:
- If selected active candidate is `>40%` more expensive than the cheapest candidate, mark status `accuracy_locked_but_cost_risky` and continue family-level refinement.
- Keep accuracy lock, but do not finalize global defaults until cost risk is reduced.

5. Family-scoped finalization:
- Finalize routing per family, not as one global winner.
- Example: keep `slices` only for families where it is uniquely required for `100%`; use `plain` on families where it is cheaper at equal hit rate.

6. Required report checks each run:
- `case_source`
- `full_hit_rate_pct`
- `tokens_per_query`
- `tokens_per_expected_hit`
- token delta between selected candidate and cheapest candidate

## Portable Validation Checklist (Any New Repo)

After running adaptation:
1. Confirm `status: ok`.
2. Confirm `case_source: generated_repo_local`.
3. Confirm `full_hit_rate_pct: 100` for selected final profile.
4. Compare selected profile vs cheapest candidate:
- if selected is much more expensive, run one rescue iteration.
5. Run a 50-query unique validation before trusting defaults broadly.

Commands:
```powershell
gcie.cmd adapt . --benchmark-size 10 --efficiency-iterations 5 --clear-profile
# mixed-layer repos: use wider calibration
gcie.cmd adapt . --benchmark-size 25 --efficiency-iterations 5 --clear-profile
```
```powershell
gcie.cmd adapt . --benchmark-size 10 --efficiency-iterations 5
```


## Remove GCIE From A Repo

To remove GCIE-managed files from the current repo:

```powershell
gcie.cmd remove .
```

Options:
- keep `GCIE_USAGE.md`: `--keep-usage`
- keep `SETUP_ANY_REPO.md`: `--keep-setup-doc`
- also remove `.planning` artifacts: `--remove-planning`

Example:

```powershell
gcie.cmd remove . --remove-planning
```








