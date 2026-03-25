"""CLI command: context."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from config.scanner_config import ScannerConfig
from graphs.call_graph import build_call_graph
from graphs.code_graph import build_code_structure_graph
from graphs.variable_graph import build_variable_graph
from llm_context.context_builder import build_context
from llm_context.snippet_selector import RankedSnippet
from parser.ast_parser import parse_python_file, parse_python_source
from retrieval.hybrid_retriever import hybrid_retrieve
from scanner.repository_scanner import scan_repository

# Simple in-process cache for repo-wide context builds
_REPO_CACHE: dict[str, tuple[nx.DiGraph, dict[str, str], dict[str, str], dict[str, str]]] = {}

_FRONTEND_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".html",
    ".vue",
}

_FRONTEND_KEYWORDS = {
    "frontend",
    "ui",
    "ux",
    "component",
    "react",
    "vue",
    "svelte",
    "angular",
    "css",
    "style",
    "layout",
    "toolbar",
    "canvas",
    "page",
    "view",
}


def _snippet_from_lines(lines: list[str], max_lines: int) -> str:
    if not lines:
        return ""
    return "\n".join(lines[:max_lines]).strip()


def _repo_signature(repo_path: Path, manifest_files) -> str:
    parts: list[str] = [repo_path.as_posix()]
    for entry in manifest_files:
        try:
            stat = (repo_path / entry.relative_path).stat()
        except OSError:
            continue
        parts.append(f"{entry.relative_path.as_posix()}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)


def _cache_dir(repo_path: Path) -> Path:
    return repo_path / ".gcie" / "cache"


def _cache_path(repo_path: Path) -> Path:
    return _cache_dir(repo_path) / "context_cache.json"


def _load_disk_cache(cache_path: Path) -> tuple[str, nx.DiGraph, dict[str, str], dict[str, str], dict[str, str]] | None:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    signature = payload.get("signature")
    graph_data = payload.get("graph")
    if signature is None or graph_data is None:
        return None

    graph = nx.node_link_graph(graph_data, directed=True)
    file_text = payload.get("file_text", {})
    function_snippets = payload.get("function_snippets", {})
    class_snippets = payload.get("class_snippets", {})
    return signature, graph, file_text, function_snippets, class_snippets


def _save_disk_cache(
    cache_path: Path,
    *,
    signature: str,
    graph: nx.DiGraph,
    file_text: dict[str, str],
    function_snippets: dict[str, str],
    class_snippets: dict[str, str],
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "signature": signature,
        "graph": nx.node_link_data(graph),
        "file_text": file_text,
        "function_snippets": function_snippets,
        "class_snippets": class_snippets,
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")


def _collect_repo_modules(repo_path: Path) -> tuple[list, dict, dict, dict, str, nx.DiGraph]:
    config = ScannerConfig.from_extensions([
        ".py",
        ".pyi",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".md",
        ".txt",
        *sorted(_FRONTEND_EXTENSIONS),
    ])
    manifest = scan_repository(repo_path, config=config)
    signature = _repo_signature(repo_path, manifest.files)

    # In-memory cache
    cache_hit = _REPO_CACHE.get(signature)
    if cache_hit is not None:
        graph, file_text, function_snippets, class_snippets = cache_hit
        return [], file_text, function_snippets, class_snippets, signature, graph

    # Disk cache
    disk_cache = _load_disk_cache(_cache_path(repo_path))
    if disk_cache is not None:
        cached_sig, graph, file_text, function_snippets, class_snippets = disk_cache
        if cached_sig == signature:
            _REPO_CACHE.clear()
            _REPO_CACHE[signature] = (graph, file_text, function_snippets, class_snippets)
            return [], file_text, function_snippets, class_snippets, signature, graph

    modules = []
    file_text: dict[str, str] = {}
    function_snippets: dict[str, str] = {}
    class_snippets: dict[str, str] = {}

    graph = nx.DiGraph()

    for entry in manifest.files:
        file_rel = entry.relative_path.as_posix()
        file_path = repo_path / entry.relative_path

        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        file_text[file_rel] = source

        # Always add file node for retrieval targeting
        file_node_id = f"file:{file_rel}"
        graph.add_node(file_node_id, type="file", label=file_rel, path=file_rel)

        if entry.suffix in {".py", ".pyi"}:
            module = parse_python_source(source, file=Path(file_rel))
            modules.append(module)

            lines = source.splitlines()
            for fn in module.functions:
                start = max(fn.start_line, 1)
                end = max(fn.end_line, start)
                snippet = "\n".join(lines[start - 1 : end]).strip()
                node_id = f"function:{Path(fn.file).as_posix()}::{fn.name}"
                if snippet:
                    function_snippets[node_id] = snippet

            for cls in module.classes:
                start = max(cls.start_line, 1)
                end = max(cls.end_line, start)
                snippet = "\n".join(lines[start - 1 : end]).strip()
                node_id = f"class:{Path(cls.file).as_posix()}::{cls.name}"
                if snippet:
                    class_snippets[node_id] = snippet

    if modules:
        graph = nx.compose(
            graph,
            nx.compose(
                nx.compose(build_call_graph(modules), build_variable_graph(modules)),
                build_code_structure_graph(modules),
            ),
        )

    _REPO_CACHE.clear()
    _REPO_CACHE[signature] = (graph, file_text, function_snippets, class_snippets)
    _save_disk_cache(
        _cache_path(repo_path),
        signature=signature,
        graph=graph,
        file_text=file_text,
        function_snippets=function_snippets,
        class_snippets=class_snippets,
    )
    return modules, file_text, function_snippets, class_snippets, signature, graph


def _frontend_bias(query: str) -> bool:
    text = query.lower()
    return any(keyword in text for keyword in _FRONTEND_KEYWORDS)


def _boost_score(node_id: str, base_score: float, query: str) -> float:
    if not _frontend_bias(query):
        return base_score
    if node_id.startswith("file:"):
        path = node_id[len("file:") :]
        suffix = Path(path).suffix.lower()
        if suffix in _FRONTEND_EXTENSIONS:
            return base_score + 0.2
    return base_score


def run_context(path: str, query: str, budget: int | None, intent: str | None) -> dict:
    target = Path(path)

    if target.is_dir():
        _, file_text, function_snippets, class_snippets, _, graph = _collect_repo_modules(target)
    else:
        module = parse_python_file(target)
        source = target.read_text(encoding="utf-8").splitlines()
        graph = nx.compose(
            nx.compose(build_call_graph((module,)), build_variable_graph((module,))),
            build_code_structure_graph((module,)),
        )
        file_rel = target.as_posix()
        file_text = {file_rel: "\n".join(source)}
        function_snippets = {}
        class_snippets = {}
        lines = source
        for fn in module.functions:
            start = max(fn.start_line, 1)
            end = max(fn.end_line, start)
            snippet = "\n".join(lines[start - 1 : end]).strip()
            node_id = f"function:{Path(fn.file).as_posix()}::{fn.name}"
            if snippet:
                function_snippets[node_id] = snippet
        for cls in module.classes:
            start = max(cls.start_line, 1)
            end = max(cls.end_line, start)
            snippet = "\n".join(lines[start - 1 : end]).strip()
            node_id = f"class:{Path(fn.file).as_posix()}::{cls.name}"
            if snippet:
                class_snippets[node_id] = snippet

    candidates = hybrid_retrieve(graph, query, top_k=20)
    ranked = []
    for c in candidates:
        snippet = function_snippets.get(c.node_id)
        if snippet is None:
            snippet = class_snippets.get(c.node_id)
        if snippet is None and c.node_id.startswith("file:"):
            file_path = c.node_id[len("file:") :]
            text = file_text.get(file_path, "")
            if text:
                snippet = _snippet_from_lines(text.splitlines(), max_lines=120)
        if snippet:
            ranked.append(
                RankedSnippet(
                    node_id=c.node_id,
                    content=snippet,
                    score=_boost_score(c.node_id, c.score, query),
                )
            )

    payload = build_context(query, ranked, token_budget=budget, intent=intent)

    return {
        "query": payload.query,
        "tokens": payload.total_tokens_estimate,
        "snippets": [
            {
                "node_id": s.node_id,
                "score": s.score,
                "content": s.content,
            }
            for s in payload.snippets
        ],
    }