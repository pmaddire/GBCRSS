"""Phase 5 variable dependency graph tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from graphs.variable_graph import build_variable_graph
from parser.ast_parser import parse_python_source


class VariableGraphTests(unittest.TestCase):
    def test_local_and_global_variable_reads_writes(self) -> None:
        source = (
            "counter = 0\n\n"
            "def update(x):\n"
            "    global counter\n"
            "    counter = counter + x\n"
            "    return counter\n"
        )
        module = parse_python_source(source, file=Path("pkg/state.py"))
        graph = build_variable_graph((module,))

        fn = "function:pkg/state.py::update"
        self.assertIn((fn, "variable:counter"), graph.edges)
        self.assertIn(graph.get_edge_data(fn, "variable:counter")["type"], {"READS", "WRITES", "MODIFIES"})

    def test_closure_attribute_and_tuple_unpacking(self) -> None:
        source = (
            "def outer():\n"
            "    val = 1\n"
            "    a, b = (2, 3)\n"
            "    class Box:\n"
            "        pass\n"
            "    box = Box()\n"
            "    box.value = val\n"
            "    def inner():\n"
            "        return box.value + a + b\n"
            "    return inner()\n"
        )
        module = parse_python_source(source, file=Path("pkg/closure.py"))
        graph = build_variable_graph((module,))

        fn = "function:pkg/closure.py::outer"
        self.assertIn((fn, "variable:a"), graph.edges)
        self.assertIn((fn, "variable:b"), graph.edges)
        self.assertIn((fn, "variable:box.value"), graph.edges)


if __name__ == "__main__":
    unittest.main()