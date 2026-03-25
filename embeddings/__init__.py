"""Embeddings package."""

from .encoder import TextEncoder
from .faiss_index import SearchHit, VectorIndex

__all__ = ["SearchHit", "TextEncoder", "VectorIndex"]