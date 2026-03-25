"""Phase 12 hybrid retriever tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import networkx as nx

from graphs.call_graph import build_call_graph
from graphs.variable_graph import build_variable_graph
from parser.ast_parser import parse_python_source
from retrieval.hybrid_retriever import hybrid_retrieve


def _graph() -> nx.DiGraph:
    source = (
        "def normalize(x):\n"
        "    return x\n\n"
        "def compute_diff(state, pred):\n"
        "    diff = state - pred\n"
        "    return normalize(diff)\n\n"
        "def run_pipeline():\n"
        "    return compute_diff(8, 2)\n"
    )
    m = parse_python_source(source, file=Path("src/core.py"))
    return nx.compose(build_call_graph((m,)), build_variable_graph((m,)))


class HybridRetrieverTests(unittest.TestCase):
    def test_hybrid_returns_ranked_candidates(self) -> None:
        graph = _graph()
        out = hybrid_retrieve(graph, "why is diff exploding", top_k=5)
        self.assertGreaterEqual(len(out), 1)
        self.assertTrue(any("diff" in c.node_id or "compute_diff" in c.node_id for c in out))

    def test_weighting_can_prioritize_git_and_coverage(self) -> None:
        graph = _graph()
        target_node = "function:src/core.py::compute_diff"

        out = hybrid_retrieve(
            graph,
            "pipeline",
            git_recency_by_node={target_node: 1.0},
            coverage_risk_by_node={target_node: 1.0},
            top_k=3,
        )
        self.assertGreaterEqual(len(out), 1)
        self.assertEqual(out[0].node_id, target_node)
        self.assertIn("git=1.0", out[0].rationale)


if __name__ == "__main__":
    unittest.main()