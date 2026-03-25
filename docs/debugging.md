# Debugging

Debugging flow follows graph-first analysis:

1. Parse query symbols
2. Identify variable/function touchpoints in graph
3. Rank candidates via hybrid retrieval
4. Build call-chain neighborhood
5. Return minimal debugging context

Primary modules:

- `debugging/bug_localizer.py`
- `debugging/execution_path_analyzer.py`
- `llm_context/context_builder.py`