# AGENT.md

Agent Operating Instructions for GraphCode Intelligence Engine (GCIE)

This file provides persistent architectural context for coding agents working on this repository.

Agents must read this file before performing any development tasks.

---

PROJECT NAME

GraphCode Intelligence Engine (GCIE)

---

PROJECT PURPOSE

GCIE is a graph-based code intelligence system designed to drastically reduce LLM token usage when working with large codebases.

Instead of sending entire files to an LLM, GCIE retrieves only the minimal execution-relevant code required to answer a query.

Example query:

"Why is variable diff exploding?"

GCIE should return only the relevant execution path and functions responsible for modifying the variable.

---

HIGH LEVEL ARCHITECTURE

The system constructs multiple graphs representing the codebase.

These graphs are combined into a unified knowledge graph used for symbolic and semantic retrieval.

Graph types include:

1. Code Structure Graph
2. Call Graph
3. Variable Dependency Graph
4. Execution Trace Graph
5. Git History Graph
6. Test Coverage Graph

---

SYSTEM COMPONENTS

parser/

Parses repository source code using AST.

Responsible for extracting:

functions
classes
variables
imports
assignments
function calls

---

graphs/

Responsible for building graph representations.

Graph modules include:

code_graph.py
call_graph.py
variable_graph.py
execution_graph.py
git_graph.py
test_graph.py

---

retrieval/

Responsible for retrieving relevant code based on queries.

Includes:

symbolic_retriever.py
semantic_retriever.py
hybrid_retriever.py

---

embeddings/

Responsible for embedding code for semantic search.

Uses SentenceTransformers.

Embeddings stored in FAISS vector index.

---

debugging/

Contains logic for automated bug localization.

Includes:

bug_localizer.py
execution_path_analyzer.py

---

llm_context/

Builds minimal code context for LLM prompts.

Responsible for formatting retrieved code snippets.

---

cli/

CLI interface for interacting with GCIE.

---

CORE DESIGN PRINCIPLES

Minimal Context Retrieval

The system should always aim to return the smallest possible code context required to answer a query.

---

Graph First Retrieval

Symbolic graph traversal should be performed before semantic search.

---

Hybrid Ranking

Final results should combine:

symbolic retrieval
semantic similarity
git recency weighting
test coverage weighting

---

GRAPH DATA MODEL

Nodes may represent:

files
classes
functions
variables
commits
tests

Edges may represent:

CALLS
IMPORTS
DEFINES
MODIFIES
READS
WRITES
EXECUTES
CHANGED_IN
COVERED_BY

---

QUERY PIPELINE

When a query is received:

1. Extract relevant symbols (variables/functions)
2. Perform symbolic graph traversal
3. Retrieve execution paths
4. Rank candidates with embeddings
5. Apply git and coverage weighting
6. Return minimal code snippets

---

BUG LOCALIZATION STRATEGY

When debugging queries are received:

1. Identify target variable or function
2. Find functions modifying that symbol
3. Trace upstream execution paths
4. Prioritize recently modified code
5. Prioritize code with low test coverage

---

DEVELOPMENT WORKFLOW

This repository uses the Get Shit Done (GSD) workflow.

Agents must follow the process:

1. Create project specification
2. Generate roadmap
3. Plan phases
4. Execute atomic tasks
5. Verify outputs

Agents must not implement large features in a single step.

---

IMPLEMENTATION RULES

Agents must:

write modular code

use Python type hints

write docstrings

verify features before continuing

follow phased development

---

PERFORMANCE GOALS

The system should aim to reduce LLM prompt context size by at least 10x compared to naive full-repository prompts.

---

FUTURE EXTENSIONS

Possible future improvements include:

cross-language support using Tree-sitter

persistent graph database using Neo4j

IDE integration

LLM agent integration

execution-aware debugging agents

---

END OF AGENT MEMORY FILE
