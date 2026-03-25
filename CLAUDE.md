# Agent Instructions

Before making any code change, run:

gcie.cmd context-slices . "<task>" --intent <edit|debug|refactor|explore>

Use only the returned snippets as working context.
If the context seems insufficient, add a pin or increase budgets.

## Tested Usage Playbook (updated 2026-03-25)

### 1) Command form

On this machine, use:

gcie.cmd context-slices . "<task>" --intent <edit|debug|refactor|explore> [--profile recall|low] [--pin <path>] [--include-tests]

(`gcie` PowerShell shim can be blocked by execution policy; `gcie.cmd` works.)

### 2) Profiles

- `--profile recall` (default): higher recall, still strong savings.
- `--profile low`: aggressive budgets, cheaper but can miss files.

Profile defaults:
- recall: stage-a 400, stage-b 800, max-total 1200, pin-budget 300
- low: stage-a 300, stage-b 600, max-total 800, pin-budget 200

### 3) Tests only when needed

Do not pull tests unless you are writing/updating tests or touching risky logic:
- Add `--include-tests` only when necessary.

### 4) File pinning for must-have wiring files

If a required file is still missing (commonly `frontend/src/App.jsx`), pin it directly:

- `gcie.cmd context-slices . "<task wiring keywords>" --pin frontend/src/App.jsx --pin-budget 300 --intent edit`

### 5) Token gate

Default max output is `--max-total 1200` tokens for medium tasks.
If required files are still missing, the tool can exceed this limit to surface more context.

### 6) Query strategy

Use explicit nouns from the code, not abstract issue summaries:

- Better: "api export endpoint doc_type session_id markdown"
- Better: "Canvas.test.jsx and Canvas.jsx for no architecture nodes generated"
- Better: "refinement rename subsystem patch persisted session outputs"

Include filenames or function/prop names where possible.

### 7) Known command behavior

- `gcie.cmd context-slices` works for repo paths and uses path-scoped slices.
- `gcie.cmd query` / `gcie.cmd debug` can fail on directory path `.` in this environment; avoid them for whole-repo lookup.
- Reindex after major changes: `gcie.cmd index .`

### 8) Sufficiency gate (required before edits)

Context is sufficient only when results include all of:

- Primary implementation file(s)
- UI/handler wiring file(s) (often `frontend/src/App.jsx`)
- At least one relevant test file (only when `--include-tests` is used)

If any are missing, add pins and/or raise budgets before editing.
