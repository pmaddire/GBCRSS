"""Hybrid symbolic + semantic retrieval pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import re

import networkx as nx

from .ranking import HybridScore, combine_score
from .semantic_retriever import SemanticRetriever
from .symbolic_retriever import symbolic_retrieve


@dataclass(frozen=True, slots=True)
class HybridCandidate:
    node_id: str
    score: float
    rationale: str


@dataclass(frozen=True, slots=True)
class HybridDiagnostics:
    query_terms: tuple[str, ...]
    symbolic_candidates: tuple[str, ...]
    semantic_candidates: tuple[str, ...]
    merged_candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SemanticAggregate:
    node_id: str
    score: float
    hit_count: int
    best_text_score: float
    lexical_overlap: int
    path_relevance: float


_STOPWORDS = {
    "how",
    "does",
    "when",
    "what",
    "why",
    "where",
    "which",
    "the",
    "this",
    "that",
    "into",
    "from",
    "with",
    "files",
    "file",
    "used",
    "using",
}


def _query_terms(query: str) -> tuple[str, ...]:
    terms = {
        part
        for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", query.lower())
        for part in token.split("_")
        if len(part) >= 3 and part not in _STOPWORDS
    }
    return tuple(sorted(terms))


def _node_path(node_id: str, attrs: dict) -> str:
    path = str(attrs.get("path") or attrs.get("file") or "")
    if path:
        return path
    if node_id.startswith("file:"):
        return node_id[5:]
    if node_id.startswith(("function:", "class:")):
        return node_id.split(":", 1)[1].split("::", 1)[0]
    return ""


def _canonical_semantic_node_id(graph: nx.DiGraph, node_id: str, attrs: dict) -> str:
    path = _node_path(node_id, attrs)
    file_node_id = f"file:{path}" if path else ""
    if file_node_id and graph.has_node(file_node_id):
        return file_node_id
    return node_id


def _lexical_overlap(node_id: str, attrs: dict, query_terms: tuple[str, ...]) -> int:
    if not query_terms:
        return 0
    label = str(attrs.get("label", ""))
    path = _node_path(node_id, attrs)
    haystack = f"{node_id} {label} {path}".lower()
    return sum(1 for term in query_terms if term in haystack)


def _path_relevance(node_id: str, attrs: dict, query_terms: tuple[str, ...]) -> float:
    if not query_terms:
        return 0.0
    path = _node_path(node_id, attrs).lower()
    if not path:
        return 0.0
    parts = {part for part in re.split(r"[^a-zA-Z0-9_]+", path) if part}
    overlap = sum(1 for term in query_terms if term in path)
    exact_parts = sum(1 for term in query_terms if term in parts)
    return overlap * 0.08 + exact_parts * 0.05


def _semantic_node_scores(
    graph: nx.DiGraph,
    query: str,
    *,
    top_k: int,
) -> tuple[dict[str, _SemanticAggregate], tuple[str, ...]]:
    query_terms = _query_terms(query)
    entries: list[tuple[str, str]] = []
    for node_id, attrs in sorted(graph.nodes(data=True), key=lambda item: item[0]):
        label = str(attrs.get("label", ""))
        path = _node_path(node_id, attrs)
        text = f"{node_id} {path} {label}".strip()
        entries.append((node_id, text))

    if not entries:
        return {}, ()

    retriever = SemanticRetriever([text for _, text in entries])
    semantic_top_k = min(max(top_k * 4, 24), len(entries))
    hits = retriever.retrieve(query, top_k=semantic_top_k)

    aggregates: dict[str, _SemanticAggregate] = {}
    raw_hits: list[str] = []
    for hit in hits:
        source_node_id, _ = entries[hit.idx]
        attrs = graph.nodes[source_node_id]
        target_node_id = _canonical_semantic_node_id(graph, source_node_id, attrs)
        target_attrs = graph.nodes[target_node_id] if graph.has_node(target_node_id) else attrs
        lexical = _lexical_overlap(target_node_id, target_attrs, query_terms)
        path_rel = _path_relevance(target_node_id, target_attrs, query_terms)
        raw_hits.append(source_node_id)

        existing = aggregates.get(target_node_id)
        hit_count = 1 if existing is None else existing.hit_count + 1
        best_text_score = hit.score if existing is None else max(existing.best_text_score, hit.score)
        best_lexical = lexical if existing is None else max(existing.lexical_overlap, lexical)
        best_path = path_rel if existing is None else max(existing.path_relevance, path_rel)
        bonus = min(0.12, 0.03 * max(hit_count - 1, 0))
        aggregate_score = min(1.0, best_text_score + bonus + min(0.08, best_lexical * 0.02) + min(0.08, best_path))
        aggregates[target_node_id] = _SemanticAggregate(
            node_id=target_node_id,
            score=aggregate_score,
            hit_count=hit_count,
            best_text_score=best_text_score,
            lexical_overlap=best_lexical,
            path_relevance=best_path,
        )

    return aggregates, tuple(raw_hits)


def collect_hybrid_diagnostics(
    graph: nx.DiGraph,
    query: str,
    *,
    git_recency_by_node: dict[str, float] | None = None,
    coverage_risk_by_node: dict[str, float] | None = None,
    max_hops: int = 2,
    top_k: int = 10,
) -> HybridDiagnostics:
    symbolic = symbolic_retrieve(graph, query, max_hops=max_hops)
    semantic, semantic_hits = _semantic_node_scores(graph, query, top_k=top_k)
    git_map = git_recency_by_node or {}
    cov_map = coverage_risk_by_node or {}
    merged = sorted(set(c.node_id for c in symbolic) | set(semantic) | set(git_map) | set(cov_map))
    return HybridDiagnostics(
        query_terms=_query_terms(query),
        symbolic_candidates=tuple(c.node_id for c in symbolic),
        semantic_candidates=semantic_hits,
        merged_candidates=tuple(merged),
    )


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
    query_terms = _query_terms(query)
    symbolic = symbolic_retrieve(graph, query, max_hops=max_hops)
    sym_distance = {c.node_id: c.distance for c in symbolic}
    semantic, _ = _semantic_node_scores(graph, query, top_k=top_k)

    git_map = git_recency_by_node or {}
    cov_map = coverage_risk_by_node or {}

    all_nodes = sorted(set(sym_distance) | set(semantic) | set(git_map) | set(cov_map))
    scored: list[HybridScore] = []

    for node_id in all_nodes:
        attrs = graph.nodes[node_id] if graph.has_node(node_id) else {}
        semantic_item = semantic.get(node_id)
        score = combine_score(
            symbolic_distance=sym_distance.get(node_id),
            semantic_score=semantic_item.score if semantic_item else None,
            git_recency=git_map.get(node_id),
            coverage_risk=cov_map.get(node_id),
        )
        scored.append(
            HybridScore(
                node_id=node_id,
                score=score,
                symbolic_distance=sym_distance.get(node_id),
                semantic_score=semantic_item.score if semantic_item else None,
                git_recency=git_map.get(node_id),
                coverage_risk=cov_map.get(node_id),
                lexical_overlap=_lexical_overlap(node_id, attrs, query_terms),
                path_relevance=_path_relevance(node_id, attrs, query_terms),
                semantic_hits=0 if semantic_item is None else semantic_item.hit_count,
            )
        )

    scored.sort(
        key=lambda s: (
            -round(s.score, 10),
            -s.lexical_overlap,
            -round(s.path_relevance, 10),
            -s.semantic_hits,
            s.symbolic_distance if s.symbolic_distance is not None else 9999,
            s.node_id,
        )
    )

    out: list[HybridCandidate] = []
    for item in scored[:top_k]:
        rationale = (
            f"symbolic_distance={item.symbolic_distance}, "
            f"semantic={item.semantic_score}, semantic_hits={item.semantic_hits}, "
            f"lexical_overlap={item.lexical_overlap}, path_relevance={item.path_relevance}, "
            f"git={item.git_recency}, coverage={item.coverage_risk}"
        )
        out.append(HybridCandidate(node_id=item.node_id, score=item.score, rationale=rationale))

    return tuple(out)
