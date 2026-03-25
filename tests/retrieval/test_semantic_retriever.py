"""Phase 11 semantic retriever tests."""

from __future__ import annotations

import unittest

from retrieval.semantic_retriever import SemanticRetriever


class SemanticRetrieverTests(unittest.TestCase):
    def test_retrieval_returns_relevant_top_hit(self) -> None:
        snippets = [
            "compute_diff updates diff and normalizes it",
            "database migration for users table",
            "http route for health check",
        ]
        retriever = SemanticRetriever(snippets)

        hits = retriever.retrieve("why does diff explode in compute_diff", top_k=2)
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("diff", hits[0].text)


if __name__ == "__main__":
    unittest.main()