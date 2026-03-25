"""Phase 8 coverage graph tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from coverage_integration.coverage_loader import CoverageFileRecord, CoverageReport
from graphs.test_graph import build_test_coverage_graph
from parser.ast_parser import parse_python_source


class TestGraphTests(unittest.TestCase):
    def test_builds_coverage_edges_for_files_and_functions(self) -> None:
        report = CoverageReport(
            files=(
                CoverageFileRecord(
                    path="src/math_ops.py",
                    executed_lines=(1, 2, 3, 7),
                    missing_lines=(8,),
                    percent_covered=80.0,
                    num_statements=5,
                    num_branches=0,
                    num_partial_branches=0,
                ),
            )
        )
        module = parse_python_source(
            "def a():\n    return 1\n\ndef b():\n    return 2\n",
            file=Path("src/math_ops.py"),
        )

        graph = build_test_coverage_graph(report, test_name="tests/test_math.py::test_a", parsed_modules=(module,))

        self.assertIn("test:tests/test_math.py::test_a", graph.nodes)
        self.assertIn("file:src/math_ops.py", graph.nodes)
        self.assertIn(("test:tests/test_math.py::test_a", "file:src/math_ops.py"), graph.edges)
        self.assertIn("function:src/math_ops.py::a", graph.nodes)


if __name__ == "__main__":
    unittest.main()