"""Phase 6 execution graph tests."""

from __future__ import annotations

import unittest

from graphs.execution_graph import build_execution_graph
from tracing.runtime_tracer import capture_trace_events


def _path(x: int) -> int:
    def step(y: int) -> int:
        return y * 2

    return step(x)


class ExecutionGraphTests(unittest.TestCase):
    def test_builds_contiguous_ordered_execution_path(self) -> None:
        events, _, err = capture_trace_events(_path, 3)
        self.assertIsNone(err)

        graph = build_execution_graph(events)

        self.assertEqual(graph.number_of_nodes(), len(events))
        if len(events) > 1:
            self.assertEqual(graph.number_of_edges(), len(events) - 1)

        orders = [attrs["order"] for _, attrs in graph.nodes(data=True)]
        self.assertEqual(sorted(orders), list(range(len(events))))

        for i in range(1, len(events)):
            prev = f"event:{i - 1}:{events[i - 1].function_name}:{events[i - 1].event}"
            curr = f"event:{i}:{events[i].function_name}:{events[i].event}"
            self.assertIn((prev, curr), graph.edges)


if __name__ == "__main__":
    unittest.main()