"""Hybrid symbolic + semantic retrieval pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from .ranking import HybridScore, combine_score
from .semantic_retriever import SemanticRetriever
from .symbolic_retriever import symbolic_retrieve


@dataclass(frozen=True, slots=True)
class HybridCandidate:
    node_id: str
    score: float
    rationale: str


def _semantic_node_scores(graph: nx.DiGraph, query: str) -> dict[str, float]:
    node_ids: list[str] = []
    snippets: list[str] = []
    for node_id, attrs in graph.nodes(data=True):
        label = str(attrs.get("label", ""))
        text = f"{node_id} {label}".strip()
        node_ids.append(node_id)
        snippets.append(text)

    retriever = SemanticRetriever(snippets)
    hits = retriever.retrieve(query, top_k=min(20, len(snippets)))

    score_map: dict[str, float] = {}
    for hit in hits:
        try:
            idx = snippets.index(hit.text)
        except ValueError:
            continue
        score_map[node_ids[idx]] = hit.score
    return score_map


def hybrid_retrieve(
    graph: nx.DiGraph,
    query: str,
    *,
    git_recency_by_node: dict[str, float] | None = None,
    coverage_risk_by_node: dict[str, float] | None = None,
    max_hops: int = 2,
    top_k: int = 10,
) -> tuple[HybridCandidate, ...]:
    """Rank retrieval candidates with hybrid weighted scoring."""
    symbolic = symbolic_retrieve(graph, query, max_hops=max_hops)
    sym_distance = {c.node_id: c.distance for c in symbolic}
    semantic = _semantic_node_scores(graph, query)

    git_map = git_recency_by_node or {}
    cov_map = coverage_risk_by_node or {}

    all_nodes = set(sym_distance).union(semantic).union(git_map).union(cov_map)
    scored: list[HybridScore] = []

    for node_id in all_nodes:
        hs = HybridScore(
            node_id=node_id,
            score=combine_score(
                symbolic_distance=sym_distance.get(node_id),
                semantic_score=semantic.get(node_id),
                git_recency=git_map.get(node_id),
                coverage_risk=cov_map.get(node_id),
            ),
            symbolic_distance=sym_distance.get(node_id),
            semantic_score=semantic.get(node_id),
            git_recency=git_map.get(node_id),
            coverage_risk=cov_map.get(node_id),
        )
        scored.append(hs)

    scored.sort(key=lambda s: (s.score, -(s.symbolic_distance or 9999)), reverse=True)

    out: list[HybridCandidate] = []
    for item in scored[:top_k]:
        rationale = (
            f"symbolic_distance={item.symbolic_distance}, "
            f"semantic={item.semantic_score}, git={item.git_recency}, coverage={item.coverage_risk}"
        )
        out.append(HybridCandidate(node_id=item.node_id, score=item.score, rationale=rationale))

    return tuple(out)