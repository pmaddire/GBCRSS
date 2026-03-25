# Retrieval

Retrieval stages:

1. Symbolic retrieval (graph-seeded)
2. Semantic retrieval (embedding/vector ranking)
3. Hybrid retrieval (symbolic + semantic + git + coverage weighting)

Key modules:

- `retrieval/symbolic_retriever.py`
- `retrieval/semantic_retriever.py`
- `retrieval/hybrid_retriever.py`
- `retrieval/ranking.py`

Outputs include ranked candidates and rationale metadata for explainability.