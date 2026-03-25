"""Test coverage graph builder."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import networkx as nx

from coverage_integration.coverage_loader import CoverageReport
from parser.models import ModuleParseResult


def _test_node_id(test_name: str) -> str:
    return f"test:{test_name}"


def _file_node_id(path: str) -> str:
    return f"file:{Path(path).as_posix()}"


def _function_node_id(path: str, fn_name: str) -> str:
    return f"function:{Path(path).as_posix()}::{fn_name}"


def build_test_coverage_graph(
    report: CoverageReport,
    *,
    test_name: str,
    parsed_modules: Iterable[ModuleParseResult] = (),
) -> nx.DiGraph:
    """Build coverage graph linking tests to covered files/functions."""
    graph = nx.DiGraph()

    test_id = _test_node_id(test_name)
    graph.add_node(test_id, type="test", label=test_name)

    module_map = {Path(m.file).as_posix(): m for m in parsed_modules}

    for rec in report.files:
        file_id = _file_node_id(rec.path)
        graph.add_node(
            file_id,
            type="file",
            label=rec.path,
            coverage_percent=rec.percent_covered,
            num_statements=rec.num_statements,
            num_branches=rec.num_branches,
            num_partial_branches=rec.num_partial_branches,
        )
        graph.add_edge(test_id, file_id, type="COVERED_BY")

        mod = module_map.get(rec.path)
        if mod is None:
            continue

        executed = set(rec.executed_lines)
        for fn in mod.functions:
            line_span = set(range(fn.start_line, fn.end_line + 1))
            if executed.intersection(line_span):
                fn_id = _function_node_id(rec.path, fn.name)
                graph.add_node(fn_id, type="function", label=fn.name, file=rec.path)
                graph.add_edge(test_id, fn_id, type="COVERED_BY")

    return graph