# PROJECT.md

## Project Name

GraphCode Intelligence Engine (GCIE)

## System Purpose

GCIE is a graph-first code intelligence engine that minimizes LLM context size for large repositories.  
It answers developer queries by retrieving only execution-relevant symbols and code snippets instead of full files.  
Primary success target: produce minimal, high-signal debugging context (for example, tracing why `diff` explodes).

## Architecture Overview

GCIE follows a staged pipeline:

1. Repository scanning discovers source files, tests, and metadata.
2. Parsing extracts symbols and relationships from source code.
3. Graph builders construct specialized graphs.
4. Knowledge index stores normalized symbol metadata for fast lookup.
5. Retrieval engine performs symbolic traversal first, then semantic ranking.
6. Context builder packages a minimal, ordered prompt payload.
7. CLI exposes indexing, querying, debugging, and diagnostics workflows.

## Core Subsystems

1. `scanner/`
Repository scanning, language filtering, include/exclude rules.

2. `parser/`
AST and Tree-sitter parsing, symbol extraction, normalized intermediate representation.

3. `graphs/`
Specialized graph construction and unified graph merge using NetworkX.

4. `knowledge_index/`
In-memory index for files/classes/functions/variables/imports/dependencies with query APIs.

5. `retrieval/`
Symbolic retriever, semantic retriever, hybrid ranking and candidate consolidation.

6. `embeddings/`
SentenceTransformers embedding generation and FAISS vector indexing.

7. `debugging/`
Bug localization and execution-path analysis workflows.

8. `llm_context/`
Minimal snippet extraction, ordering, deduplication, and context packaging.

9. `cli/`
Typer-based commands for index/build/query/debug/report operations.

10. `tests/`
Unit, integration, coverage, and retrieval quality validation.

## Graph Models

GCIE maintains these graph models and composes them into a unified knowledge graph:

1. Code Structure Graph
Nodes: files, modules, classes, functions.  
Edges: `DEFINES`, `CONTAINS`, `IMPORTS`.

2. Call Graph
Nodes: callable symbols.  
Edges: `CALLS`.

3. Variable Dependency Graph
Nodes: variables, functions, assignments.  
Edges: `READS`, `WRITES`, `MODIFIES`.

4. Execution Trace Graph
Nodes: runtime function frames/events.  
Edges: `EXECUTES`, `RETURNS`, temporal path edges.

5. Git History Graph
Nodes: commits, files, symbols.  
Edges: `CHANGED_IN`, `TOUCHES`.

6. Test Coverage Graph
Nodes: tests, functions, files.  
Edges: `COVERED_BY`, `ASSERTS_ON`.

7. Unified Knowledge Graph
Merged, queryable graph used by retrieval and bug localization.

## Retrieval Pipeline

1. Query ingestion
Normalize query text and identify query intent (`debug`, `trace`, `dependency`, `explain`).

2. Symbol extraction
Extract candidate symbols (variable/function/class/file/module names).

3. Knowledge index lookup
Resolve exact/fuzzy symbol matches and seed candidate nodes.

4. Symbolic graph traversal
Traverse variable/call/structure/trace graphs for execution-relevant neighborhood.

5. Semantic retrieval
Use embeddings + FAISS to rank semantically similar snippets among symbolic candidates.

6. Hybrid ranking
Combine symbolic distance, semantic score, git recency, and test coverage risk weighting.

7. Minimal context assembly
Return only necessary snippets: symbol definition, writes/modifies points, callers/callees, and trace path.

8. Output formatting
Provide structured debugging payload: relevant functions, call chain, variable modifications, evidence scores.

## GSD Workflow Contract

1. Plan before implementation.
2. Execute in phases with atomic tasks.
3. Verify each phase before advancing.
4. Keep artifacts updated (`PROJECT.md`, `ROADMAP.md`, and phase plans).
5. Do not implement large features in a single step.

## Initial Constraints

1. Language/runtime: Python 3.11+.
2. Parsers: `ast` first, Tree-sitter extension path.
3. Graph engine: NetworkX.
4. Semantic layer: SentenceTransformers + FAISS.
5. Git analysis: GitPython.
6. Execution tracing: `sys.settrace`.
7. Coverage: Coverage.py.
8. CLI: Typer.
9. Retrieval principle: symbolic first, semantic second.

## Success Criteria

1. Repository indexing works across project files.
2. Core graph suite is built and queryable.
3. Symbolic + semantic hybrid retrieval returns ranked candidates.
4. Debug query returns compact execution-relevant context only.
5. End-to-end token usage is materially reduced versus full-file prompting.

