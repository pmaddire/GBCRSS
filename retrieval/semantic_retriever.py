"""Semantic retriever implementation."""

from __future__ import annotations

from dataclasses import dataclass

from embeddings.encoder import TextEncoder
from embeddings.faiss_index import VectorIndex


@dataclass(frozen=True, slots=True)
class SemanticCandidate:
    idx: int
    text: str
    score: float


class SemanticRetriever:
    """Semantic retrieval over text snippets."""

    def __init__(self, snippets: list[str]) -> None:
        self._snippets = snippets
        self._encoder = TextEncoder()
        self._index = VectorIndex()

        vectors = self._encoder.encode(snippets)
        self._index.add(vectors)

    def retrieve(self, query: str, top_k: int = 5) -> tuple[SemanticCandidate, ...]:
        qvec = self._encoder.encode([query])[0]
        hits = self._index.search(qvec, top_k=top_k)

        out: list[SemanticCandidate] = []
        for hit in hits:
            if hit.idx < 0 or hit.idx >= len(self._snippets):
                continue
            out.append(SemanticCandidate(idx=hit.idx, text=self._snippets[hit.idx], score=hit.score))

        return tuple(out)
