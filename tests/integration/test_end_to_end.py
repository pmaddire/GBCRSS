"""Phase 17 end-to-end tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import networkx as nx

from debugging.bug_localizer import localize_bug
from graphs.call_graph import build_call_graph
from graphs.variable_graph import build_variable_graph
from llm_context.context_builder import build_context
from llm_context.snippet_selector import RankedSnippet
from parser.ast_parser import parse_python_source


class EndToEndTests(unittest.TestCase):
    def test_index_to_debug_context_flow(self) -> None:
        source = (
            "def normalize(x):\n"
            "    return x\n\n"
            "def compute_diff(a,b):\n"
            "    diff = a-b\n"
            "    return normalize(diff)\n\n"
            "def run():\n"
            "    return compute_diff(3,1)\n"
        )
        module = parse_python_source(source, file=Path("src/e2e.py"))
        graph = nx.compose(build_call_graph((module,)), build_variable_graph((module,)))

        report = localize_bug(graph, "why is diff exploding")
        snippets = [
            RankedSnippet(node_id=n, content=f"snippet for {n}", score=1.0 - i * 0.1)
            for i, n in enumerate(report.ranked_candidates[:5])
        ]

        payload = build_context(
            "why is diff exploding",
            snippets,
            token_budget=40,
            mandatory_node_ids={next(iter(report.variable_modifications), "")},
        )

        self.assertGreaterEqual(len(report.relevant_functions), 1)
        self.assertGreaterEqual(len(payload.snippets), 1)
        self.assertLessEqual(payload.total_tokens_estimate, 40)


if __name__ == "__main__":
    unittest.main()