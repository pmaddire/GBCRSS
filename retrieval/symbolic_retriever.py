"""Symbolic retriever over GCIE graphs."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import networkx as nx

from .query_parser import ParsedQuery, parse_query


@dataclass(frozen=True, slots=True)
class SymbolicCandidate:
    node_id: str
    node_type: str
    distance: int


def _symbol_matches(text: str, symbol: str) -> bool:
    t = text.lower()
    s = symbol.lower()
    return s == t or s in t


def _seed_nodes(graph: nx.DiGraph, parsed: ParsedQuery) -> list[str]:
    seeds: list[str] = []
    for node_id, attrs in graph.nodes(data=True):
        label = str(attrs.get("label", ""))
        path = str(attrs.get("path", attrs.get("file", "")))
        if any(_symbol_matches(node_id, sym) or _symbol_matches(label, sym) or _symbol_matches(path, sym) for sym in parsed.symbols):
            seeds.append(node_id)
    return sorted(set(seeds))


def _bounded_traversal(graph: nx.DiGraph, seeds: list[str], max_hops: int) -> dict[str, int]:
    distances: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque((seed, 0) for seed in seeds)

    while queue:
        node, dist = queue.popleft()
        if node in distances and dist >= distances[node]:
            continue
        distances[node] = dist

        if dist >= max_hops:
            continue

        neighbors = set(graph.predecessors(node)).union(graph.successors(node))
        for nxt in neighbors:
            queue.append((nxt, dist + 1))

    return distances


def symbolic_retrieve(graph: nx.DiGraph, query: str, *, max_hops: int = 2) -> tuple[SymbolicCandidate, ...]:
    """Retrieve symbolic candidates by seeded graph traversal."""
    parsed = parse_query(query)
    if not parsed.symbols:
        return ()

    seeds = _seed_nodes(graph, parsed)
    if not seeds:
        return ()

    distances = _bounded_traversal(graph, seeds, max_hops=max_hops)

    ranked: list[SymbolicCandidate] = []
    for node_id, dist in distances.items():
        attrs = graph.nodes[node_id]
        ranked.append(
            SymbolicCandidate(
                node_id=node_id,
                node_type=str(attrs.get("type", "unknown")),
                distance=dist,
            )
        )

    ranked.sort(key=lambda c: (c.distance, c.node_type, c.node_id))
    return tuple(ranked)