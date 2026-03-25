"""Phase 10 symbolic retriever tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import networkx as nx

from graphs.call_graph import build_call_graph
from graphs.variable_graph import build_variable_graph
from parser.ast_parser import parse_python_source
from retrieval.symbolic_retriever import symbolic_retrieve


def _build_composite_graph() -> nx.DiGraph:
    source = (
        "def normalize(x):\n"
        "    return x\n\n"
        "def compute_diff(state, pred):\n"
        "    diff = state - pred\n"
        "    return normalize(diff)\n\n"
        "def run():\n"
        "    return compute_diff(3, 1)\n"
    )
    module = parse_python_source(source, file=Path("src/engine.py"))

    call_graph = build_call_graph((module,))
    var_graph = build_variable_graph((module,))

    merged = nx.compose(call_graph, var_graph)
    return merged


class SymbolicRetrieverTests(unittest.TestCase):
    def test_retrieves_multi_hop_candidates(self) -> None:
        graph = _build_composite_graph()

        results = symbolic_retrieve(graph, "Why is variable diff exploding?", max_hops=2)
        ids = [r.node_id for r in results]

        self.assertTrue(any("variable:diff" == node_id for node_id in ids))
        self.assertTrue(any("compute_diff" in node_id for node_id in ids))

    def test_returns_empty_for_missing_symbol(self) -> None:
        graph = _build_composite_graph()
        results = symbolic_retrieve(graph, "What about missing_symbol_zzz?", max_hops=2)
        self.assertEqual(results, ())

    def test_handles_ambiguous_symbols(self) -> None:
        graph = _build_composite_graph()
        # 'run' appears in function label and node id.
        results = symbolic_retrieve(graph, "run", max_hops=1)
        self.assertTrue(any("::run" in r.node_id for r in results))


if __name__ == "__main__":
    unittest.main()