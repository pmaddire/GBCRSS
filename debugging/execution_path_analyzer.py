"""Execution path analysis helpers for debugging output."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True, slots=True)
class ExecutionPath:
    nodes: tuple[str, ...]
    reason: str


def shortest_path_between(graph: nx.DiGraph, source: str, target: str) -> ExecutionPath | None:
    """Return shortest undirected path between two nodes when available."""
    try:
        path = nx.shortest_path(graph.to_undirected(), source=source, target=target)
        return ExecutionPath(nodes=tuple(path), reason="shortest_undirected_path")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def neighborhood_path(graph: nx.DiGraph, seed: str, hops: int = 2) -> ExecutionPath:
    """Return bounded BFS neighborhood around a seed node."""
    seen = {seed}
    frontier = {seed}

    for _ in range(max(hops, 0)):
        nxt: set[str] = set()
        for node in frontier:
            nxt.update(graph.predecessors(node))
            nxt.update(graph.successors(node))
        nxt -= seen
        if not nxt:
            break
        seen.update(nxt)
        frontier = nxt

    ordered = tuple(sorted(seen))
    return ExecutionPath(nodes=ordered, reason=f"neighborhood_hops={hops}")