"""Phase 16 benchmark and cache tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import networkx as nx

from graphs.call_graph import build_call_graph
from graphs.graph_store import GraphStore
from parser.ast_parser import parse_python_source
from performance.profiler import profile_call
from retrieval.cache import RetrievalCache
from retrieval.symbolic_retriever import symbolic_retrieve


class PerformanceBenchmarkTests(unittest.TestCase):
    def test_cache_roundtrip(self) -> None:
        cache = RetrievalCache()
        cache.set("q:diff", ("function:a", "variable:diff"))
        self.assertEqual(cache.get("q:diff"), ("function:a", "variable:diff"))

    def test_graph_store_snapshot_copy(self) -> None:
        graph = nx.DiGraph()
        graph.add_node("n1")

        store = GraphStore()
        store.put("v1", graph)
        loaded = store.get("v1")

        self.assertIsNotNone(loaded)
        assert loaded is not None
        loaded.add_node("n2")
        self.assertNotIn("n2", store.get("v1").nodes)

    def test_symbolic_retrieval_profile(self) -> None:
        source = (
            "def compute_diff(a,b):\n"
            "    diff = a-b\n"
            "    return diff\n"
            "def run():\n"
            "    return compute_diff(2,1)\n"
        )
        module = parse_python_source(source, file=Path("src/mod.py"))
        graph = build_call_graph((module,))

        _, prof = profile_call("symbolic", symbolic_retrieve, graph, "diff", max_hops=2)
        self.assertGreaterEqual(prof.duration_ms, 0.0)


if __name__ == "__main__":
    unittest.main()