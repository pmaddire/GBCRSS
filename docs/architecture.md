# Architecture

GCIE pipeline:

Repository -> Scanner -> Parser -> Graph Builders -> Knowledge Index -> Retrieval -> LLM Context -> CLI

Implemented graph components:

- Code structure graph
- Call graph
- Variable dependency graph
- Execution trace graph
- Git history graph
- Test coverage graph

All graph modules expose deterministic builders and are validated by tests.