# GCIE Hybrid Workflow (In-Progress Draft)

Status:
- Working draft for active tuning.
- Not final policy yet.
- Goal: push efficiency higher without losing the current perfect-recall behavior on the hybrid benchmark workflow.

## Why This Workflow

The current best tradeoff observed in external testing was:

- Average tokens: `1479.0`
- Average token savings: `78.6%`
- Average accuracy: `100%`
- Full-hit rate: `100%`

This is better than fully decomposed retrieval on efficiency, while keeping the same full coverage.

## Core Rule

Use a two-stage hybrid flow, not one-shot and not full decomposition by default:

1. Primary retrieval pass with task-shaped budget.
2. Gap-fill only missing must-have files with targeted follow-up calls.
3. Stop as soon as must-have coverage is complete.

## Must-Have Coverage Gate

Treat context as sufficient only if it includes:

- primary implementation file(s)
- wiring/caller/orchestrator file(s)
- at least one validation/test surface when behavior risk is non-trivial

If any must-have file is missing, run targeted gap-fill.

## Query Construction

Best-performing query shape:

1. file-first
2. symbol-heavy
3. concrete flow terms
4. include caller/entry when target is indirect

Pattern:

```text
<file-a> <file-b> <function/component> <state-or-arg> <route/flag> <config-key>
```

## Budget Policy (Task-Shape Aware)

Start at the smallest budget likely to satisfy the shape.

- `auto`: simple same-layer and strong single-file lookups
- `900`: near-miss two-file lookups
- `1100`: backend/config/orchestration chains
- `1150`: cross-layer UI/API chains
- `1200`: fallback if 1100/1150 still miss one must-have file
- `1300-1400`: only for clearly multi-hop stage-pair or 3+ file chains

## Hybrid Execution Steps

### Step 1: Primary pass

```powershell
gcie.cmd context . "<file-first symbol-heavy query>" --intent <edit|debug|refactor|explore> --budget <shape budget>
```

### Step 2: Evaluate must-have coverage

If missing files remain, run targeted file queries only for missing files:

```powershell
gcie.cmd context <missing-file-path> "<missing-file> <key symbols>" --intent <edit|debug|refactor|explore> --budget 300
```

Use `300-500` for gap-fill. Do not rerun broad root query unless multiple families are still missing.

### Step 3: Stop condition

Stop immediately when must-have coverage is complete.

Do not continue increasing budgets after sufficiency is reached.

## Long Chain Rule

For 4+ file chains, decompose into adjacent hops instead of one oversized query.

Example:

1. upstream -> middle
2. middle -> downstream

Merge results and dedupe by file path.

## Verification Rule

Always verify with `rg` before edits:

```powershell
rg -n "symbol1|symbol2|symbol3" <likely files>
```

GCIE is the context compressor, not the final truth gate.

## Quick Recipes

### Cross-layer UI/API

```powershell
gcie.cmd context . "frontend/src/App.jsx app.py start_convert /api/convert/start /api/jobs selectedTheme" --intent edit --budget 1150
```

### Backend/config pair

```powershell
gcie.cmd context . "llm_client.py main.py backend_info OPENAI_API_KEY no_ai" --intent explore --budget 1100
```

### Builder/orchestrator

```powershell
gcie.cmd context . "main.py Plan_slides.py Build_pptx.py Stage 3 Stage 4 plan build_pptx" --intent edit --budget 1200
```

### Multi-hop chain

```powershell
gcie.cmd context . "Analyze_pdf_structure.py Plan_slides.py split_into_sections section_name" --intent refactor --budget 1000
gcie.cmd context . "Plan_slides.py Extract_pdf_content.py extract_tables figure_slides" --intent refactor --budget 1000
```

## Current Optimization Direction

In-progress focus for next efficiency gains while preserving accuracy:

1. tighter trigger for gap-fill so it fires only when truly needed
2. smaller targeted gap-fill snippets by default
3. stronger de-prioritization of low-signal support/config neighbors when explicit targets exist
4. better root-path locality bias when explicit file targets cluster in one subtree
