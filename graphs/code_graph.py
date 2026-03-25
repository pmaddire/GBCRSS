"""Code structure graph builder."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import networkx as nx

from parser.models import ModuleParseResult

from .node_factory import (
    class_node_id,
    file_node_id,
    function_node_id,
    module_node_id,
)


def _normalize_path(file_path: Path, root: Path | None) -> Path:
    if root is None:
        return file_path
    try:
        return file_path.resolve().relative_to(root.resolve())
    except ValueError:
        return file_path


def build_code_structure_graph(
    modules: Iterable[ModuleParseResult],
    *,
    root: Path | None = None,
) -> nx.DiGraph:
    """Build file/class/function/import structural graph from parsed modules."""
    graph = nx.DiGraph()

    for module in modules:
        rel_file = _normalize_path(module.file, root)
        file_id = file_node_id(rel_file)
        graph.add_node(
            file_id,
            type="file",
            label=rel_file.as_posix(),
            path=rel_file.as_posix(),
        )

        for cls in module.classes:
            class_id = class_node_id(rel_file, cls.name)
            graph.add_node(
                class_id,
                type="class",
                label=cls.name,
                file=rel_file.as_posix(),
                start_line=cls.start_line,
                end_line=cls.end_line,
            )
            graph.add_edge(file_id, class_id, type="DEFINES")
            graph.add_edge(file_id, class_id, type="CONTAINS")

        for fn in module.functions:
            function_id = function_node_id(rel_file, fn.name)
            graph.add_node(
                function_id,
                type="function",
                label=fn.name,
                file=rel_file.as_posix(),
                start_line=fn.start_line,
                end_line=fn.end_line,
            )
            graph.add_edge(file_id, function_id, type="DEFINES")
            graph.add_edge(file_id, function_id, type="CONTAINS")

        for imp in module.imports:
            import_targets = imp.names if imp.names else ((imp.module,) if imp.module else ())
            for symbol in import_targets:
                module_name = f"{imp.module}.{symbol}" if imp.module else symbol
                module_id = module_node_id(module_name)
                graph.add_node(module_id, type="module", label=module_name)
                graph.add_edge(file_id, module_id, type="IMPORTS")

    return graph