"""Call graph builder."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import networkx as nx

from parser.call_resolver import resolve_calls
from parser.models import ModuleParseResult

from .node_factory import function_node_id


def _normalize_path(file_path: Path, root: Path | None) -> Path:
    if root is None:
        return file_path
    try:
        return file_path.resolve().relative_to(root.resolve())
    except ValueError:
        return file_path


def build_call_graph(modules: Iterable[ModuleParseResult], *, root: Path | None = None) -> nx.DiGraph:
    """Build caller-callee graph with unresolved external call nodes preserved."""
    graph = nx.DiGraph()

    module_list = list(modules)
    for module in module_list:
        rel_file = _normalize_path(module.file, root)
        for fn in module.functions:
            node_id = function_node_id(rel_file, fn.name)
            graph.add_node(
                node_id,
                type="function",
                label=fn.name,
                file=rel_file.as_posix(),
                qualified_name=f"{rel_file.as_posix()}::{fn.name}",
            )

    local_name_to_node: dict[tuple[str, str], str] = {}
    for module in module_list:
        rel_file = _normalize_path(module.file, root)
        for fn in module.functions:
            local_name_to_node[(rel_file.as_posix(), fn.name)] = function_node_id(rel_file, fn.name)

    for module in module_list:
        rel_file = _normalize_path(module.file, root)
        for resolved in resolve_calls(module):
            caller_id = local_name_to_node[(rel_file.as_posix(), resolved.caller)]

            if resolved.resolved:
                callee_id = local_name_to_node.get((rel_file.as_posix(), resolved.callee))
                if callee_id is None:
                    # Should not happen for local resolution, but keep graph robust.
                    callee_id = f"external:{resolved.callee}"
                    graph.add_node(callee_id, type="external_function", label=resolved.callee)
            else:
                callee_id = f"external:{resolved.callee}"
                graph.add_node(callee_id, type="external_function", label=resolved.callee)

            graph.add_edge(
                caller_id,
                callee_id,
                type="CALLS",
                resolved=resolved.resolved,
            )

    return graph