# DEBUGGING_PLAYBOOK.md

GraphCode Intelligence Engine Debugging Playbook

This document describes how agents should debug problems using the GCIE graph system.

Agents must follow this structured debugging workflow instead of guessing.

---

DEBUGGING PRINCIPLES

Always prioritize structural analysis before semantic guessing.

Use graph queries whenever possible.

Only use LLM reasoning after symbolic analysis.

---

DEBUGGING WORKFLOW

When debugging a problem, follow this procedure.

Step 1 — Identify Target Symbols

Extract relevant symbols from the query.

Examples:

variable names
function names
file names
modules

Example query:

"Why is variable diff exploding?"

Target symbol:

diff

---

Step 2 — Query Knowledge Index

Use the knowledge index to find:

functions that modify the variable
functions that read the variable

Example query:

find functions writing variable diff

---

Step 3 — Trace Variable Dependencies

Use the variable dependency graph.

Identify:

where the variable is modified
which functions depend on it

---

Step 4 — Trace Call Graph

From functions modifying the variable:

trace upstream callers

trace downstream calls

This reveals execution paths that influence the variable.

---

Step 5 — Analyze Execution Paths

Use the execution trace graph when available.

Identify the runtime path leading to the issue.

---

Step 6 — Prioritize Suspicious Code

Rank candidate functions using:

recent git commits

low test coverage

large code complexity

---

Step 7 — Build Minimal Debugging Context

Return only the relevant functions:

the function modifying the variable

its callers

any functions it calls

---

EXAMPLE DEBUGGING FLOW

Query:

"Why is diff exploding?"

Process:

extract symbol → diff

query knowledge index → functions modifying diff

trace variable graph → compute_diff()

trace call graph → update_state() → run_simulation()

retrieve minimal code context

---

DEBUGGING HEURISTICS

Prefer code that:

modifies the target variable

recently changed in git

has low test coverage

appears frequently in execution traces

---

DEBUGGING OUTPUT FORMAT

When returning debugging results include:

relevant functions

call chain

variable modifications

---

END DEBUGGING PLAYBOOK
