"""Phase 6 runtime tracer tests."""

from __future__ import annotations

import unittest

from tracing.runtime_tracer import capture_trace_events


def _fib(n: int) -> int:
    if n <= 1:
        return n
    return _fib(n - 1) + _fib(n - 2)


def _explode() -> None:
    raise ValueError("boom")


def _calls_chain(x: int) -> int:
    def inner(y: int) -> int:
        return y + 1

    return inner(x)


class RuntimeTracerTests(unittest.TestCase):
    def test_traces_recursive_calls(self) -> None:
        events, result, err = capture_trace_events(_fib, 4)

        self.assertIsNone(err)
        self.assertEqual(result, 3)
        names = [e.function_name for e in events if e.event == "call"]
        self.assertIn("_fib", names)
        self.assertGreaterEqual(names.count("_fib"), 5)

    def test_traces_exception_event(self) -> None:
        events, result, err = capture_trace_events(_explode)

        self.assertIsNone(result)
        self.assertIsNotNone(err)
        self.assertTrue(any(e.event == "exception" and e.function_name == "_explode" for e in events))

    def test_traces_multi_function_flow(self) -> None:
        events, result, err = capture_trace_events(_calls_chain, 2)

        self.assertIsNone(err)
        self.assertEqual(result, 3)
        calls = [e.function_name for e in events if e.event == "call"]
        self.assertIn("_calls_chain", calls)
        self.assertIn("inner", calls)


if __name__ == "__main__":
    unittest.main()