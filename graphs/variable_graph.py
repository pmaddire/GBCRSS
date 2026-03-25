"""Variable dependency graph builder."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import networkx as nx

from parser.models import ModuleParseResult
from parser.variable_extractor import extract_variable_dependencies

from .node_factory import function_node_id


def _normalize_path(file_path: Path, root: Path | None) -> Path:
    if root is None:
        return file_path
    try:
        return file_path.resolve().relative_to(root.resolve())
    except ValueError:
        return file_path


def _variable_node_id(name: str) -> str:
    return f"variable:{name}"


def build_variable_graph(modules: Iterable[ModuleParseResult], *, root: Path | None = None) -> nx.DiGraph:
    """Build function-variable dependency graph with READS/WRITES/MODIFIES edges."""
    graph = nx.DiGraph()

    for module in modules:
        rel_file = _normalize_path(module.file, root)

        for fn in module.functions:
            fn_id = function_node_id(rel_file, fn.name)
            graph.add_node(
                fn_id,
                type="function",
                label=fn.name,
                file=rel_file.as_posix(),
            )

        for dep in extract_variable_dependencies(module):
            fn_id = function_node_id(rel_file, dep.function_name)
            var_id = _variable_node_id(dep.variable_name)
            graph.add_node(var_id, type="variable", label=dep.variable_name)
            graph.add_edge(fn_id, var_id, type=dep.access_type)

    return graph