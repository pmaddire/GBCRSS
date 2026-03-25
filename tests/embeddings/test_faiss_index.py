"""Phase 11 vector index tests."""

from __future__ import annotations

import unittest

from embeddings.faiss_index import VectorIndex


class VectorIndexTests(unittest.TestCase):
    def test_add_and_search_returns_ranked_hits(self) -> None:
        index = VectorIndex()
        vectors = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.8, 0.2, 0.0],
        ]
        index.add(vectors)

        hits = index.search([1.0, 0.0, 0.0], top_k=2)
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].idx, 0)


if __name__ == "__main__":
    unittest.main()