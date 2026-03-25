# ROADMAP.md

## Roadmap: GraphCode Intelligence Engine (GCIE)

## Overview

This roadmap follows the GSD workflow: define phased outcomes, execute atomic tasks, verify phase outputs, then proceed sequentially.  
No implementation begins until the phase plan is approved and phase execution starts.

## Phases

1. Repository Scanning
2. AST Parsing Engine
3. Code Structure Graph
4. Call Graph
5. Variable Dependency Graph
6. Execution Trace Graph
7. Git History Graph
8. Test Coverage Graph
9. Knowledge Index
10. Symbolic Retrieval System
11. Semantic Retrieval System
12. Hybrid Retrieval Pipeline
13. Bug Localization System
14. LLM Context Builder
15. CLI Interface
16. Performance Optimization
17. Testing and Documentation

## Phase Plans (Atomic Tasks)

### Phase 1: Repository Scanning
Goal: Discover indexable repository artifacts and produce normalized file manifests.

Task 1.1
Target files: `scanner/repository_scanner.py`, `scanner/file_filters.py`, `scanner/models.py`
Implementation instructions: build recursive scanner, extension filters, ignore rules, and manifest dataclasses.
Verification steps: run scanner on sample repo; confirm deterministic manifest output.
Completion criteria: scanner returns stable list of source/test/config files with metadata.

Task 1.2
Target files: `config/scanner_config.py`, `tests/scanner/test_repository_scanner.py`
Implementation instructions: add include/exclude config model and tests for hidden dirs, large files, and unsupported extensions.
Verification steps: execute scanner tests and inspect edge-case fixtures.
Completion criteria: scanner behavior is configurable and validated by passing tests.

### Phase 2: AST Parsing Engine
Goal: Parse Python code and emit normalized symbol-level IR.

Task 2.1
Target files: `parser/ast_parser.py`, `parser/models.py`
Implementation instructions: implement AST walker extracting modules, classes, functions, parameters, docstrings, assignments, imports, calls.
Verification steps: parse fixture files and assert extracted symbols/line ranges.
Completion criteria: parser emits complete symbol IR for valid Python files.

Task 2.2
Target files: `parser/tree_sitter_adapter.py`, `tests/parser/test_parser_fallbacks.py`
Implementation instructions: define Tree-sitter adapter interface and fallback policy when AST parsing is unavailable or partial.
Verification steps: simulate fallback scenarios using malformed fixtures.
Completion criteria: parser pipeline provides predictable fallback behavior with tests.

### Phase 3: Code Structure Graph
Goal: Build structural relationships between files, classes, and functions.

Task 3.1
Target files: `graphs/code_graph.py`, `graphs/node_factory.py`
Implementation instructions: map IR entities to graph nodes and create `DEFINES`, `CONTAINS`, and `IMPORTS` edges.
Verification steps: graph snapshot tests on fixture projects.
Completion criteria: structure graph is connected and queryable by symbol/file.

Task 3.2
Target files: `tests/graphs/test_code_graph.py`, `graphs/validators.py`
Implementation instructions: add integrity checks for node uniqueness, edge consistency, and missing references.
Verification steps: run graph validation tests against positive and negative fixtures.
Completion criteria: invalid graph states are detected and reported.

### Phase 4: Call Graph
Goal: Build function-to-function call relationships.

Task 4.1
Target files: `graphs/call_graph.py`, `parser/call_resolver.py`
Implementation instructions: resolve local and module-qualified calls; add `CALLS` edges with source location metadata.
Verification steps: test direct calls, nested calls, and method calls.
Completion criteria: call graph captures expected caller-callee chains.

Task 4.2
Target files: `tests/graphs/test_call_graph.py`
Implementation instructions: create fixtures for recursion, alias imports, and unresolved external calls.
Verification steps: execute tests and verify unresolved calls are labeled, not dropped.
Completion criteria: call graph behavior is deterministic for known edge cases.

### Phase 5: Variable Dependency Graph
Goal: Model read/write/modify relationships for variables.

Task 5.1
Target files: `graphs/variable_graph.py`, `parser/variable_extractor.py`
Implementation instructions: detect variable definitions, reads, writes, and updates; create `READS`, `WRITES`, `MODIFIES` edges.
Verification steps: run tests on assignment and mutation patterns.
Completion criteria: variable graph correctly identifies modifier functions for target variables.

Task 5.2
Target files: `tests/graphs/test_variable_graph.py`
Implementation instructions: add fixtures for local/global scope, closures, attributes, and tuple unpacking.
Verification steps: assert correct scope attribution and edge generation.
Completion criteria: variable dependency extraction is validated for common Python patterns.

### Phase 6: Execution Trace Graph
Goal: Capture runtime execution paths and map traces to symbols.

Task 6.1
Target files: `graphs/execution_graph.py`, `tracing/runtime_tracer.py`
Implementation instructions: implement `sys.settrace` event capture and transform call/return events into execution graph edges.
Verification steps: run tracer on deterministic sample program and compare trace order.
Completion criteria: execution trace graph reproduces runtime path with timestamped edges.

Task 6.2
Target files: `tests/tracing/test_runtime_tracer.py`, `tests/graphs/test_execution_graph.py`
Implementation instructions: add tests for recursion, exceptions, and multi-function flows.
Verification steps: validate path continuity and symbol mapping in traces.
Completion criteria: trace graph is reliable for debugging path reconstruction.

### Phase 7: Git History Graph
Goal: Relate commits to files and symbols for recency-aware ranking.

Task 7.1
Target files: `graphs/git_graph.py`, `git_integration/git_miner.py`
Implementation instructions: ingest commit history via GitPython and map changed files/symbol spans to `CHANGED_IN` edges.
Verification steps: run against fixture repo with known commit history.
Completion criteria: graph exposes commit recency and symbol touch history.

Task 7.2
Target files: `tests/git/test_git_miner.py`, `tests/graphs/test_git_graph.py`
Implementation instructions: validate rename handling, author/date extraction, and empty history behavior.
Verification steps: run tests using temporary repositories.
Completion criteria: git graph ingestion is resilient and test-covered.

### Phase 8: Test Coverage Graph
Goal: Map tests to covered symbols and files.

Task 8.1
Target files: `graphs/test_graph.py`, `coverage_integration/coverage_loader.py`
Implementation instructions: import Coverage.py results and link tests to functions/files using `COVERED_BY` edges.
Verification steps: run sample tests with coverage and compare expected mappings.
Completion criteria: coverage graph quantifies coverage for retrieval weighting.

Task 8.2
Target files: `tests/coverage/test_coverage_loader.py`, `tests/graphs/test_test_graph.py`
Implementation instructions: test partial coverage, missing reports, and branch coverage metadata.
Verification steps: execute loader and graph tests.
Completion criteria: coverage integration handles both complete and sparse reports.

### Phase 9: Knowledge Index
Goal: Provide fast metadata lookup for symbols and dependencies.

Task 9.1
Target files: `knowledge_index/models.py`, `knowledge_index/index_builder.py`, `knowledge_index/store.py`
Implementation instructions: implement in-memory entries for files, classes, functions, variables, imports, dependencies.
Verification steps: build index from fixture IR and assert entry completeness.
Completion criteria: index supports required entry formats and lookups.

Task 9.2
Target files: `knowledge_index/query_api.py`, `tests/knowledge_index/test_query_api.py`
Implementation instructions: implement queries: variable modifiers, callers, imports, inheritance.
Verification steps: run query API tests against known fixtures.
Completion criteria: index answers core structural queries without LLM calls.

### Phase 10: Symbolic Retrieval System
Goal: Retrieve execution-relevant candidates via graph traversal.

Task 10.1
Target files: `retrieval/symbolic_retriever.py`, `retrieval/query_parser.py`
Implementation instructions: extract symbols/intents and perform seeded traversal across structure/call/variable/trace graphs.
Verification steps: evaluate retrieval on debugging query fixtures.
Completion criteria: symbolic retriever returns focused candidate subgraphs.

Task 10.2
Target files: `tests/retrieval/test_symbolic_retriever.py`
Implementation instructions: add tests for ambiguous symbols, missing symbols, and multi-hop traversal limits.
Verification steps: run tests and inspect ranked symbolic results.
Completion criteria: symbolic retrieval precision is acceptable on benchmark fixtures.

### Phase 11: Semantic Retrieval System
Goal: Rank code candidates by semantic relevance.

Task 11.1
Target files: `embeddings/encoder.py`, `embeddings/faiss_index.py`, `retrieval/semantic_retriever.py`
Implementation instructions: generate embeddings, maintain FAISS index, and return similarity-ranked snippets.
Verification steps: run embedding/index smoke tests on fixture corpus.
Completion criteria: semantic retriever returns deterministic top-k results.

Task 11.2
Target files: `tests/retrieval/test_semantic_retriever.py`, `tests/embeddings/test_faiss_index.py`
Implementation instructions: validate indexing, updates, persistence hooks, and retrieval quality thresholds.
Verification steps: execute test suite and compare expected rankings.
Completion criteria: semantic retrieval module is stable and test-covered.

### Phase 12: Hybrid Retrieval Pipeline
Goal: Fuse symbolic and semantic retrieval with risk weighting.

Task 12.1
Target files: `retrieval/hybrid_retriever.py`, `retrieval/ranking.py`
Implementation instructions: combine symbolic distance, semantic score, git recency, and coverage risk into final rank.
Verification steps: run controlled ranking scenarios with synthetic weights.
Completion criteria: hybrid ranking is explainable and configurable.

Task 12.2
Target files: `tests/retrieval/test_hybrid_retriever.py`
Implementation instructions: assert ranking order for debugging scenarios and regression fixtures.
Verification steps: run tests and verify rationale metadata in output.
Completion criteria: hybrid pipeline consistently improves relevance over symbolic-only baseline.

### Phase 13: Bug Localization System
Goal: Produce structured root-cause candidates for debugging queries.

Task 13.1
Target files: `debugging/bug_localizer.py`, `debugging/execution_path_analyzer.py`
Implementation instructions: implement workflow from symbol extraction to modifier detection and upstream/downstream path tracing.
Verification steps: run end-to-end bug-localization fixtures (including `diff`-style queries).
Completion criteria: output includes relevant functions, call chain, and variable modifications.

Task 13.2
Target files: `tests/debugging/test_bug_localizer.py`
Implementation instructions: test ranking heuristics for recent commits, low coverage, and frequent execution paths.
Verification steps: execute tests and review explanation payload.
Completion criteria: bug-localization quality meets defined fixture expectations.

### Phase 14: LLM Context Builder
Goal: Build minimal, ordered context payloads for LLM prompts.

Task 14.1
Target files: `llm_context/context_builder.py`, `llm_context/snippet_selector.py`
Implementation instructions: select minimal snippets from ranked candidates; deduplicate and preserve execution order.
Verification steps: compare output token estimates with full-file baseline.
Completion criteria: context builder emits compact payloads with traceable provenance.

Task 14.2
Target files: `tests/llm_context/test_context_builder.py`
Implementation instructions: add tests for token-budget clipping, snippet overlap, and mandatory-symbol retention.
Verification steps: run tests and ensure deterministic output for fixed inputs.
Completion criteria: context output is reproducible and bounded by budget.

### Phase 15: CLI Interface
Goal: Expose GCIE capabilities through Typer commands.

Task 15.1
Target files: `cli/app.py`, `cli/commands/index.py`, `cli/commands/query.py`, `cli/commands/debug.py`
Implementation instructions: implement commands for indexing, graph build, retrieval query, and debug report.
Verification steps: run CLI help and command smoke tests in fixture workspace.
Completion criteria: users can execute end-to-end flow from CLI without direct Python API use.

Task 15.2
Target files: `tests/cli/test_cli_commands.py`
Implementation instructions: add CLI integration tests with fixture repositories and expected output schemas.
Verification steps: execute CLI tests and validate exit codes plus structured output.
Completion criteria: CLI is reliable for automation and local usage.

### Phase 16: Performance Optimization
Goal: Reduce indexing/query latency and memory cost while preserving relevance.

Task 16.1
Target files: `performance/profiler.py`, `retrieval/cache.py`, `graphs/graph_store.py`
Implementation instructions: add profiling instrumentation, caching, and incremental graph/index refresh paths.
Verification steps: run benchmark scenarios before/after optimization.
Completion criteria: measurable gains in indexing/query runtime and memory footprint.

Task 16.2
Target files: `tests/performance/test_benchmarks.py`, `docs/performance.md`
Implementation instructions: define benchmark suite and acceptance thresholds for latency/token reduction.
Verification steps: execute benchmark tests and capture baseline report.
Completion criteria: performance targets are versioned and regression-tested.

### Phase 17: Testing and Documentation
Goal: Finalize quality gates and project documentation.

Task 17.1
Target files: `tests/integration/test_end_to_end.py`, `tests/regression/test_query_regressions.py`
Implementation instructions: create end-to-end tests from indexing to minimal context output for canonical debugging queries.
Verification steps: run full test suite with coverage enabled.
Completion criteria: integration and regression suites pass with acceptable coverage.

Task 17.2
Target files: `README.md`, `docs/architecture.md`, `docs/retrieval.md`, `docs/debugging.md`
Implementation instructions: document architecture, phase outcomes, CLI usage, and troubleshooting workflow.
Verification steps: follow docs to execute first-time setup and sample query run.
Completion criteria: documentation supports onboarding and reproducible operation.

## Sequential Execution Rules

1. Phases execute in numeric order (1 through 17).
2. Do not start a phase until previous phase completion criteria are satisfied.
3. If a phase fails verification, fix within the same phase before proceeding.
4. Record verification evidence after each phase.
5. Re-scope only through roadmap update, not ad hoc implementation.

## Milestone Outcome Targets

1. Repository indexing and graph construction are operational.
2. Symbolic + semantic hybrid retrieval is operational.
3. Debugging flow returns minimal execution-relevant context.
4. CLI and documentation enable practical day-to-day use.

