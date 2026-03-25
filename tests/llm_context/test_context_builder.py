"""Phase 14 context builder tests."""

from __future__ import annotations

import unittest

from llm_context.context_builder import build_context
from llm_context.snippet_selector import RankedSnippet


class ContextBuilderTests(unittest.TestCase):
    def test_budget_clipping_and_selection_order(self) -> None:
        ranked = [
            RankedSnippet("n1", "alpha beta gamma", 0.9),
            RankedSnippet("n2", "delta epsilon", 0.8),
            RankedSnippet("n3", "zeta eta theta iota", 0.7),
        ]
        payload = build_context("q", ranked, token_budget=5)

        self.assertGreaterEqual(len(payload.snippets), 1)
        self.assertLessEqual(payload.total_tokens_estimate, 5)

    def test_deduplicates_overlapping_content(self) -> None:
        ranked = [
            RankedSnippet("n1", "same content", 0.9),
            RankedSnippet("n2", "same content", 0.8),
            RankedSnippet("n3", "different", 0.7),
        ]
        payload = build_context("q", ranked, token_budget=20)

        contents = [s.content for s in payload.snippets]
        self.assertEqual(contents.count("same content"), 1)

    def test_retains_mandatory_symbol_when_budget_allows(self) -> None:
        ranked = [
            RankedSnippet("must", "must keep", 0.1),
            RankedSnippet("best", "best content", 0.9),
        ]
        payload = build_context("q", ranked, token_budget=10, mandatory_node_ids={"must"})

        ids = {s.node_id for s in payload.snippets}
        self.assertIn("must", ids)


if __name__ == "__main__":
    unittest.main()