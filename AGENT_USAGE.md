# GCIE Workflow For The New `context` Command

This guide is for the newer repo-local `gcie.cmd context` workflow.

Goal:
- keep context small
- pull the real implementation files, not just nearby entrypoints
- raise budget only when the query shape truly needs it

GCIE is best used as a first-pass context compressor, not as the final source of truth. After retrieval, still verify with a fast local search such as `rg`.

## 1) Default Command

Start with:

```powershell
gcie.cmd context . "<query>" --intent <edit|debug|refactor|explore>
```

Only add `--budget` if the result misses an important file or if you already know the task is multi-hop.

## 2) Core Query Rule

The best-performing queries were:

1. file-first
2. symbol-heavy
3. concrete
4. cross-layer when needed

That means the query should usually include:

- 1 to 3 explicit file paths
- 2 to 6 distinctive symbols
- any endpoint, CLI flag, config key, route, or option that ties the files together

Good pattern:

```text
<primary-file> <secondary-file> <function-or-component> <state-or-arg> <endpoint-or-flag> <config-key>
```

Examples:

```powershell
gcie.cmd context . "frontend/src/App.jsx selectedTheme activeJobId export default function App" --intent edit

gcie.cmd context . "frontend/src/App.jsx app.py start_convert /api/convert/start /api/jobs selectedTheme" --intent edit

gcie.cmd context . "Build_pptx.py main.py build_pptx THEME_CHOICES args.theme" --intent edit

gcie.cmd context . "llm_client.py app.py main.py backend_info OPENAI_API_KEY no_ai" --intent explore
```

## 3) What To Avoid

Avoid vague summaries:

- `fix upload flow`
- `theme issue`
- `OpenAI bug`
- `component problem`

Avoid filename-only queries for UI files when possible:

- `frontend/src/App.jsx`

That often pulls the file family or entrypoint instead of the actual component.

Avoid overspecifying many unrelated files in one query. GCIE does better with one path through the system than with a laundry list.

## 4) Query Construction Rules

### A) Single-file query

If you want one file, do not use only the filename. Add strong symbols from inside the file.

Use:

```text
<file> <exported symbol> <state var> <helper fn> <prop or option>
```

Example:

```powershell
gcie.cmd context . "frontend/src/App.jsx export default function App selectedTheme API_BASE" --intent edit
```

Observed pattern:
- single backend/service files were usually fine with `auto`
- single frontend component files often needed stronger symbols to avoid drifting to the app entrypoint

### B) Same-layer query

If both files live in the same layer, name both files and 2 to 4 connecting symbols.

Use:

```text
<file-a> <file-b> <shared symbol> <imported symbol> <state or helper>
```

Examples:

```powershell
gcie.cmd context . "frontend/src/App.jsx frontend/src/main.jsx selectedTheme API_BASE" --intent edit

gcie.cmd context . "llm_client.py main.py backend_info OPENAI_API_KEY no_ai" --intent explore
```

Observed pattern:
- same-layer two-file queries usually worked well with `auto`

### C) Cross-layer query

If the task crosses UI/API, caller/callee, orchestrator/worker, or config/runtime boundaries, include both ends of the path and the thing that flows between them.

Use:

```text
<upstream-file> <downstream-file> <function-or-handler> <endpoint-or-flag> <state-or-config-key>
```

Examples:

```powershell
gcie.cmd context . "frontend/src/App.jsx app.py start_convert /api/convert/start /api/jobs selectedTheme" --intent edit

gcie.cmd context . "Build_pptx.py main.py build_pptx THEME_CHOICES args.theme" --intent edit

gcie.cmd context . "llm_client.py app.py main.py backend_info OPENAI_API_KEY no_ai" --intent explore
```

Observed pattern:
- cross-layer queries improve a lot when both endpoint files are named
- backend/config/orchestration queries are the most likely to need a larger budget

### D) Caller-anchor rule

If GCIE misses a target implementation file, add its caller, importer, entrypoint, or handler file.

This worked especially well for:

- builder/generator modules
- components reached through an entry file
- library/config files used indirectly by an app/server/orchestrator

Examples:

```powershell
gcie.cmd context . "Build_pptx.py main.py build_pptx THEME_CHOICES render_eq_png" --intent edit

gcie.cmd context . "frontend/src/App.jsx frontend/src/main.jsx export default function App selectedTheme" --intent edit
```

If the target file is not directly tied to an external route, flag, or API surface, adding the caller file is often better than adding more internal symbols alone.

## 5) Budget Ladder

Use this budget ladder instead of jumping straight to a large number.

### Step 1: `auto`

Start here for:

- same-layer tasks
- backend/service lookups
- two-file tasks with obvious symbols
- quick exploration

### Step 2: `900` to `1000`

Use this when:

- `auto` found most of the path but missed one important file
- the query is cross-layer but only 2 files wide
- the result is close but underpacked

### Step 3: `1200`

Use this for:

- cross-layer edits
- backend/config/orchestration lookups
- UI to API lookups
- builder/orchestrator flows
- cases where `auto` missed one hop of a three-file chain

This was the most reliable high-value budget in testing. It usually fixed recall without adding too much extra noise.

### Step 4: above `1200`

Only go above `1200` if:

- you still miss a required file after improving the query
- the task clearly spans more than three meaningful files
- verification shows one more hop is still missing

Do not raise the budget automatically just because the output contains some noise. More budget often adds neighbors faster than it adds signal.

## 6) Practical Budget Rules By Task Type

### Single backend/service file

Recommended:
- `auto`

If missed:
- improve symbols before raising budget

### Single frontend component

Recommended:
- `auto`, but include strong in-file symbols

If missed:
- add the entry/importer file
- then try `900` or `1000`

### Same-layer multi-file task

Recommended:
- `auto`

If one file is missing:
- improve the connecting symbols
- then try `900`

### Cross-layer UI/API task

Recommended:
- `auto` if the query already names both ends and the endpoint/state symbols
- otherwise go directly to `1000` or `1200`

### Cross-layer backend/config/orchestration task

Recommended:
- `1200`

This is the task family most likely to be under-budgeted by `auto`.

### Builder/generator reached from an orchestrator

Recommended:
- include both the target module and its caller
- use `1000` or `1200` if `auto` misses the target module

## 7) How To Tell If The Query Is Under-Budgeted

Common signs:

- GCIE returns nearby family files but misses the target implementation file
- it returns the app entrypoint but not the component/module you asked for
- it returns helper/config neighbors but misses the worker/orchestrator file
- it finds 2 of 3 required files in a chain

When that happens:

1. improve the query shape first
2. rerun at `900` or `1000`
3. if the task is truly cross-layer, rerun at `1200`

## 8) Verification Rule

After every GCIE lookup, verify the result with fast local search before editing.

Example:

```powershell
rg -n "symbol1|symbol2|symbol3" <likely files>
```

Context is sufficient only when you have:

- the main implementation file
- any caller/handler/orchestrator file that feeds it
- any route, config, or state-passing file that affects behavior
- relevant tests, if you are editing tests or behavior covered by tests

If GCIE misses one of those, use `rg` to find it and read that file directly.

## 9) Retrieval Recipes

### Quick same-layer lookup

```powershell
gcie.cmd context . "<file-a> <file-b> <shared symbols>" --intent explore
```

### UI component lookup

```powershell
gcie.cmd context . "<component-file> <component symbol> <state var> <entry file>" --intent edit
```

### API flow lookup

```powershell
gcie.cmd context . "<frontend-file> <backend-file> <handler> <route> <state or form key>" --intent edit --budget 1000
```

### Orchestration lookup

```powershell
gcie.cmd context . "<worker-file> <caller-file> <function> <flag> <config key>" --intent explore --budget 1200
```

## 10) PowerShell Notes

Prefer plain quoted queries and keep them shell-safe.

Good:

```powershell
gcie.cmd context . "app.py start_convert /api/convert/start selectedTheme" --intent edit
```

Safer than embedding lots of punctuation-heavy placeholders when you do not need them:

- `/api/jobs_job_id/download`

instead of:

- `/api/jobs/{job_id}/download`

Both can work, but simpler tokens tend to be easier to reason about across shells and tokenizers.

## 11) Recommended Workflow

1. Write a file-first, symbol-heavy query.
2. Start with `auto` unless the task is obviously cross-layer and multi-hop.
3. If the result misses one hop, improve the query before increasing budget.
4. Raise to `900` or `1000` for near-miss cases.
5. Raise to `1200` for real cross-layer or orchestration tasks.
6. Verify with `rg`.
7. Read only the confirmed files.
8. Edit.

## 12) Bottom Line

The new `gcie.cmd context` is worth using, but it performs best when:

- the query names real files
- the query includes concrete symbols, not summaries
- caller/entry files are included when the target is indirect
- budget is raised based on task shape, not by default

Most important rule:

- fix the query shape first
- fix the budget second

That gives better recall without spending tokens unnecessarily.
