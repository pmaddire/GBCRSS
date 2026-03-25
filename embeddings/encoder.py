"""Embedding encoder with SentenceTransformers fallback."""

from __future__ import annotations

import hashlib
import math
from typing import Iterable


def _fallback_vector(text: str, dims: int = 64) -> list[float]:
    vec = [0.0] * dims
    tokens = text.lower().split()
    if not tokens:
        return vec

    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class TextEncoder:
    """SentenceTransformer-compatible text encoder with deterministic fallback."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(model_name)
        except Exception:
            self._model = None

    def encode(self, texts: Iterable[str]) -> list[list[float]]:
        values = list(texts)
        if self._model is not None:
            vectors = self._model.encode(values, normalize_embeddings=True)
            return [list(map(float, row)) for row in vectors]

        return [_fallback_vector(text) for text in values]