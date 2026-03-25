"""FAISS-compatible vector index with in-memory fallback."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchHit:
    idx: int
    score: float


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class VectorIndex:
    """Vector index that prefers FAISS and falls back to brute-force cosine."""

    def __init__(self) -> None:
        self._faiss = None
        self._index = None
        self._vectors: list[list[float]] = []

        try:
            import faiss  # type: ignore

            self._faiss = faiss
        except Exception:
            self._faiss = None

    def add(self, vectors: list[list[float]]) -> None:
        if not vectors:
            return

        if self._faiss is None:
            self._vectors.extend(vectors)
            return

        import numpy as np

        arr = np.array(vectors, dtype="float32")
        if self._index is None:
            dim = arr.shape[1]
            self._index = self._faiss.IndexFlatIP(dim)
        self._index.add(arr)

    def search(self, query: list[float], top_k: int = 5) -> tuple[SearchHit, ...]:
        if top_k <= 0:
            return ()

        if self._faiss is None:
            scored = [SearchHit(idx=i, score=_dot(query, vec)) for i, vec in enumerate(self._vectors)]
            scored.sort(key=lambda h: h.score, reverse=True)
            return tuple(scored[:top_k])

        import numpy as np

        if self._index is None or self._index.ntotal == 0:
            return ()

        q = np.array([query], dtype="float32")
        scores, indices = self._index.search(q, top_k)

        hits: list[SearchHit] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            hits.append(SearchHit(idx=int(idx), score=float(score)))
        return tuple(hits)