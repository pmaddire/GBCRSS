"""Graph validation helpers."""

from __future__ import annotations

import networkx as nx


REQUIRED_NODE_ATTRS = {"type", "label"}


def validate_graph_integrity(graph: nx.DiGraph) -> list[str]:
    """Return a list of graph integrity errors, empty when valid."""
    errors: list[str] = []

    for node, attrs in graph.nodes(data=True):
        missing = REQUIRED_NODE_ATTRS.difference(attrs.keys())
        if missing:
            errors.append(f"node {node} missing attrs: {', '.join(sorted(missing))}")

    for source, target, attrs in graph.edges(data=True):
        if source not in graph.nodes:
            errors.append(f"edge source missing: {source}")
        if target not in graph.nodes:
            errors.append(f"edge target missing: {target}")
        if "type" not in attrs:
            errors.append(f"edge {source}->{target} missing type")

    return errors