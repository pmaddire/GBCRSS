# GCIE Hybrid Workflow For The New `context` Command

Status:
- accuracy-first working workflow
- benchmarked on the 50-query suite in this repo
- tuned to keep full-hit behavior, then recover efficiency where safe

## Why This Workflow

The best stable workflow from this round was:

- Average tokens: `1503.4`
- Average token savings: `78.5%`
- Average accuracy: `100%`
- Full-hit rate: `100%`

A more aggressive variant with smaller gap-fill budgets got average tokens down to `1418.6`, but accuracy dropped to `98.3%` and full-hit rate dropped to `96%`, so it is not the recommended default.

## Core Rule

Use a two-stage hybrid flow:

1. Primary retrieval pass with task-shaped budget.
2. Gap-fill only the missing must-have files.
3. Stop as soon as must-have coverage is complete.

Do not default to one giant repo-root query.
Do not default to full decomposition either.

## Must-Have Coverage Gate

Treat context as sufficient only if it includes:

- primary implementation file(s)
- wiring, caller, or orchestrator file(s)
- one validation surface when behavior risk is non-trivial

If any must-have file is missing, run targeted gap-fill.
If must-have coverage is complete, stop immediately.

## Query Construction

Best-performing query shape:

`<file-a> <file-b> <function/component> <state-or-arg> <route/flag> <config-key>`

Use:
- explicit file paths
- 2 to 6 distinctive symbols
- route strings, flags, config keys, stage markers, state vars
- caller or entry file when the target is indirect

Avoid:
- vague intent-only summaries
- giant laundry-list queries
- repo-root filename-only frontend queries

## Path Rule

Use the narrowest path that still contains the file you need.

Use:
- `frontend` for frontend-local component recovery
- `.` for backend, orchestrator, and true cross-layer retrieval

Important:
- frontend gap-fill worked best as subtree-scoped retrieval
- missing backend Python modules worked better with repo-root targeted queries than file-path calls

## Budget Policy

Start with the smallest budget that usually satisfies the task shape.

Primary pass defaults:
- `auto`: strong single backend files and simple same-layer lookups
- `900`: single frontend subtree retrieval, simple builder lookups, some stage queries
- `1000`: adjacent-hop or stage-2 builder queries
- `1100`: same-layer backend or backend/config pairs
- `1150`: cross-layer UI/API queries
- `1400`: stage-pair builder/orchestrator and some 3-file chain queries

Gap-fill defaults:
- `900` for missing `frontend/src/App.jsx` using `frontend` scope
- `500` for missing `main.py`
- `900` for missing backend implementation files such as:
  - `app.py`
  - `Build_pptx.py`
  - `Plan_slides.py`
  - `Analyze_pdf_structure.py`
  - `Extract_pdf_content.py`
  - `llm_client.py`

Why these are higher than the draft:
- `300-500` gap-fill was too weak for missing backend modules in this repo
- `700` worked often, but it regressed benchmark accuracy on a few hard cases
- `900` was the smallest stable setting that preserved full recall here

## Workflow Steps

### Step 1: Primary pass

```powershell
gcie.cmd context <path> "<file-first symbol-heavy query>" --intent <edit|debug|refactor|explore> --budget <shape budget>
```

### Step 2: Evaluate must-have coverage

If files are missing, run targeted gap-fill only for the missing file.

Frontend-local missing file:
```powershell
gcie.cmd context frontend "src/App.jsx src/main.jsx <key symbols>" --intent edit --budget 900
```

Missing backend Python file:
```powershell
gcie.cmd context . "<missing-file> <key symbols>" --intent <intent> --budget 900
```

Missing `main.py`:
```powershell
gcie.cmd context . "main.py <stage markers or key symbols>" --intent <intent> --budget 500
```

Do not rerun a broader repo-root query unless multiple core families are still missing.

### Step 3: Stop condition

Stop as soon as must-have coverage is complete.

Do not keep increasing budget after sufficiency is reached.

## Task-Shaped Recipes

### Single frontend component

```powershell
gcie.cmd context frontend "src/App.jsx src/main.jsx export default function App selectedTheme API_BASE" --intent edit --budget 900
```

### Single backend/service file

```powershell
gcie.cmd context . "llm_client.py call_text _openai_post json_mode" --intent explore
```

### Same-layer frontend pair

```powershell
gcie.cmd context . "frontend/src/App.jsx frontend/src/main.jsx React createRoot App" --intent edit
```

### Same-layer backend pair

```powershell
gcie.cmd context . "Extract_pdf_content.py llm_client.py enrich_with_ai call_vision backend_info" --intent explore --budget 1100
gcie.cmd context . "Analyze_pdf_structure.py Plan_slides.py split_into_sections section_name" --intent refactor --budget 1000
```

If one file is still missing, run a targeted gap-fill for that file at `900`.

### Cross-layer UI/API

Primary:
```powershell
gcie.cmd context . "frontend/src/App.jsx app.py start_convert /api/convert/start /api/jobs selectedTheme" --intent edit --budget 1150
```

If `frontend/src/App.jsx` is missing:
```powershell
gcie.cmd context frontend "src/App.jsx src/main.jsx start_convert selectedTheme activeJobId" --intent edit --budget 900
```

If `app.py` is missing:
```powershell
gcie.cmd context . "app.py start_convert selected_theme selectedTheme no_ai" --intent edit --budget 900
```

### Builder/orchestrator

```powershell
gcie.cmd context . "Build_pptx.py main.py build_pptx render_eq_png args.theme" --intent edit --budget 900
gcie.cmd context . "main.py Plan_slides.py Build_pptx.py Stage 3 Stage 4 build_content_slide content_slides" --intent edit --budget 1400
gcie.cmd context . "main.py Extract_pdf_content.py extract_images enrich_with_ai Stage 2" --intent explore --budget 1000
```

If one implementation file is missing, fill only that file:
```powershell
gcie.cmd context . "Build_pptx.py build_pptx render_eq_png apply_theme THEME_CHOICES" --intent edit --budget 900
gcie.cmd context . "Plan_slides.py content_slides section_divider figure_slides table_slide" --intent explore --budget 900
gcie.cmd context . "main.py Stage 3 Stage 4 plan content_slides" --intent explore --budget 500
```

### Multi-hop chain

```powershell
gcie.cmd context . "llm_client.py Analyze_pdf_structure.py Extract_pdf_content.py call_text call_vision backend_info" --intent refactor --budget 1300
gcie.cmd context . "Analyze_pdf_structure.py Extract_pdf_content.py Plan_slides.py split_into_sections extract_tables plan" --intent explore --budget 1100
gcie.cmd context . "main.py Plan_slides.py Build_pptx.py Stage 3 Stage 4 plan build_pptx" --intent explore --budget 1400
```

If one stage file is missing, gap-fill only that file at `900` or `500` for `main.py`.

If more than one stage file is missing, decompose into adjacent hops instead of one oversized query.

## Long Chain Rule

For 4+ file chains:
1. try the strongest narrow one-shot first
2. if one stage is missing, gap-fill that stage only
3. if multiple stages are missing, split into adjacent hops

Example:
```powershell
gcie.cmd context . "Analyze_pdf_structure.py Plan_slides.py split_into_sections section_name" --intent refactor --budget 1000
gcie.cmd context . "Plan_slides.py Extract_pdf_content.py extract_tables figure_slides" --intent refactor --budget 1000
```

## Verification Rule

Always verify with `rg` before editing.

```powershell
rg -n "symbol1|symbol2|symbol3" <likely files>
```

GCIE is the context compressor, not the final truth gate.

## Recommended Workflow

1. Classify the task shape.
2. Start with the cheapest high-confidence primary pass.
3. Check must-have coverage.
4. If one file is missing, gap-fill only that file.
5. Use `frontend` scope for frontend-local recovery.
6. Use repo-root targeted queries for missing backend Python modules.
7. Use `500` for missing `main.py`.
8. Use `900` for missing backend implementation modules and frontend component recovery.
9. If multiple core families are still missing, decompose into hops.
10. Verify with `rg`.
11. Read only the confirmed files.
12. Edit.

## Bottom Line

The current best stable workflow is:
- one-shot first where hit rate is already good
- targeted gap-fill for only the missing file
- subtree fallback for frontend components
- repo-root targeted gap-fill for missing backend Python modules
- full decomposition only when more than one important stage is still missing

Most important rule:
- keep the successful first pass
- fill only the missing file
- stop as soon as coverage is complete
