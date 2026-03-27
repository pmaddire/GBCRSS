"""CLI command: context."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from config.scanner_config import ScannerConfig
from graphs.call_graph import build_call_graph
from graphs.code_graph import build_code_structure_graph
from graphs.variable_graph import build_variable_graph
from llm_context.context_builder import build_context
from llm_context.snippet_selector import RankedSnippet, estimate_tokens
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

_CODE_EXTENSIONS = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    *sorted(_FRONTEND_EXTENSIONS),
}

_DOC_EXTENSIONS = {".md", ".txt", ".rst"}

_ALL_CONTEXT_EXTENSIONS = _CODE_EXTENSIONS | _DOC_EXTENSIONS

_EXCLUDE_GLOBS = (
    "get-shit-done/docs/ja-JP/**",
    "get-shit-done/docs/zh-CN/**",
)

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
    "hook",
    "hooks",
}

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
    "help",
    "doesnt",
    "using",
    "used",
}

_OPERATIONAL_DOC_NAMES = {
    "agent.md",
    "agent_usage.md",
    "architecture.md",
    "project.md",
    "roadmap.md",
    "debugging_playbook.md",
    "readme.md",
    "skill.md",
    "claude.md",
    "contextgrabber.md",
}

_OPERATIONAL_PATH_HINTS = (
    ".planning/",
    ".gcie/",
    "/skills/",
    "get-shit-done/workflows/",
    "get-shit-done/commands/",
    "get-shit-done/templates/",
)

_QUERY_ALIASES = {
    "routing": ("router", "route"),
    "router": ("routing", "route"),
    "bootstrapped": ("bootstrap", "init", "initialize", "managed"),
    "bootstrapping": ("bootstrap", "init", "initialize", "managed"),
    "bootstrap": ("init", "initialize", "managed", "index", "architecture"),
    "managed": ("index", "architecture"),
    "command": ("cli", "handler", "run", "context"),
    "commands": ("cli", "handler", "run", "context"),
    "context": ("builder", "command", "cli"),
    "pipeline": ("retrieval", "hybrid", "symbolic", "semantic", "ranking"),
    "retrieval": ("pipeline", "hybrid", "symbolic", "semantic", "ranking"),
    "hybrid": ("retrieval", "symbolic", "semantic", "ranking"),
    "builder": ("build", "index", "context"),
    "builders": ("builder", "build", "index", "context"),
    "build": ("builder", "context"),
    "plan": ("planner", "pipeline", "stage"),
    "planner": ("plan", "pipeline", "stage"),
    "convert": ("conversion", "api", "route"),
    "conversion": ("convert", "api", "route"),
    "analyze": ("analysis", "pipeline", "stage"),
    "analysis": ("analyze", "pipeline", "stage"),
    "extract": ("extraction", "pipeline", "stage"),
    "extraction": ("extract", "pipeline", "stage"),
    "stage": ("pipeline", "plan", "build"),
    "stages": ("stage", "pipeline", "plan", "build"),
    "scanning": ("scanner", "scan", "repository"),
    "scanner": ("scanning", "scan", "repository"),
    "tracing": ("trace", "tracer", "execution"),
    "represented": ("representation", "represent", "execution"),
    "generate": ("generation", "agent", "model", "stream"),
    "refine": ("refinement", "patch", "chat", "model"),
    "wiring": ("app", "main", "entry", "route", "router"),
}

_GENERIC_ENTRYPOINT_STEMS = {"main", "index", "app"}
_GENERIC_ENTRYPOINT_PATHS = {
    "frontend/src/main.jsx",
    "frontend/index.html",
}
_BACKEND_PATH_HINTS = ("backend/", "server/", "api/", "services/", "service/", "workers/", "worker/")
_BACKEND_FILE_HINTS = (
    "client",
    "service",
    "worker",
    "controller",
    "handler",
    "router",
    "route",
    "config",
    "settings",
    "pipeline",
    "plan",
    "build",
    "extract",
    "analyze",
)
_CHAIN_TERMS = {
    "stage",
    "stages",
    "pipeline",
    "plan",
    "planner",
    "build",
    "builder",
    "convert",
    "analyze",
    "extract",
    "workflow",
}
_COMMON_FAMILY_TOKENS = {
    "src",
    "tests",
    "test",
    "commands",
    "command",
    "context",
    "cli",
    "core",
    "app",
    "file",
    "files",
    "index",
    "init",
    "main",
}

_SYSTEM_QUERY_TERMS = {
    "architecture",
    "bootstrap",
    "command",
    "commands",
    "context",
    "pipeline",
    "retrieval",
    "workflow",
    "builder",
    "builders",
    "graph",
    "routing",
    "router",
    "generate",
    "refine",
    "wiring",
}

_SUPPORT_ROLE_TOKENS = {
    "app",
    "main",
    "index",
    "entry",
    "router",
    "route",
    "context",
    "builder",
    "hook",
    "hooks",
    "provider",
    "service",
    "client",
    "store",
    "state",
    "handler",
    "controller",
    "bootstrap",
    "command",
    "commands",
    "retriever",
    "selector",
    "evaluator",
    "parser",
    "scanner",
    "generate",
    "refine",
}

_SUPPORT_PROMOTION_TERMS = {
    "routing",
    "router",
    "fallback",
    "bootstrap",
    "managed",
    "index",
    "builder",
    "build",
    "command",
    "commands",
    "context",
    "orchestration",
    "workflow",
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


def _effective_intent(query: str, intent: str | None) -> str:
    if intent:
        return intent
    text = query.lower()
    if any(word in text for word in ("debug", "why", "error", "fail", "bug", "trace")):
        return "debug"
    if any(word in text for word in ("refactor", "rewrite", "migrate", "restructure")):
        return "refactor"
    if any(word in text for word in ("add", "change", "update", "extend", "modify", "remove", "rename")):
        return "edit"
    return "explore"


def _query_terms(query: str) -> set[str]:
    raw_terms = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", query.lower())
    terms: set[str] = set()
    for term in raw_terms:
        for part in term.split("_"):
            if len(part) >= 3 and part not in _STOPWORDS:
                terms.add(part)
                for alias in _QUERY_ALIASES.get(part, ()):
                    if len(alias) >= 3 and alias not in _STOPWORDS:
                        terms.add(alias)
    return terms


def _is_system_query(query: str) -> bool:
    return bool(_query_terms(query) & _SYSTEM_QUERY_TERMS)


def _classify_path(path: str) -> str:
    candidate = Path(path)
    suffix = candidate.suffix.lower()
    lowered = candidate.as_posix().lower()
    name = candidate.name.lower()

    if suffix in _CODE_EXTENSIONS:
        return "code"
    if suffix not in _DOC_EXTENSIONS:
        return "general_doc"
    if name in _OPERATIONAL_DOC_NAMES:
        return "operational_doc"
    if any(hint in lowered for hint in _OPERATIONAL_PATH_HINTS):
        return "operational_doc"
    if "/plans/" in lowered or lowered.endswith("-plan.md") or lowered.endswith("-context.md"):
        return "operational_doc"
    return "general_doc"


def _normalized_query_text(query: str) -> str:
    return query.lower().replace('\\', '/')


def _explicit_file_mention_score(path: str, query: str) -> float:
    normalized_query = _normalized_query_text(query)
    normalized_path = path.lower().replace('\\', '/')
    candidate = Path(path)
    name = candidate.name.lower()
    stem = candidate.stem.lower()
    score = 0.0
    if normalized_path and normalized_path in normalized_query:
        score += 1.2
    if name and name in normalized_query:
        score += 0.75
    if stem and re.search(rf"\b{re.escape(stem)}\b", normalized_query):
        score += 0.2
    return min(1.6, score)


def _mentioned_file_paths(file_text: dict[str, str], query: str) -> list[tuple[float, str]]:
    matches: list[tuple[float, str]] = []
    for rel_path in file_text:
        score = _explicit_file_mention_score(rel_path, query)
        if score <= 0:
            continue
        matches.append((score, rel_path))
    matches.sort(key=lambda item: (-item[0], item[1]))
    return matches


def _layer_bucket(path: str | None) -> str:
    if not path:
        return "unknown"
    normalized = path.lower().replace("\\", "/")
    if normalized.startswith(("frontend/", "ui/", "web/")):
        return "frontend"
    if normalized.startswith(("backend/", "server/", "api/")):
        return "backend"
    if normalized.startswith(("tests/", "test/")):
        return "test"
    if normalized.startswith(("docs/", ".gcie/")) or normalized.endswith(".md"):
        return "docs"
    if any(token in normalized for token in ("build", "theme", "pptx", "worker", "job")):
        return "build"
    candidate = Path(path)
    if candidate.parts:
        return candidate.parts[0].lower()
    return candidate.stem.lower()



def _is_edit_like_query(query: str, intent: str | None) -> bool:
    effective = _effective_intent(query, intent)
    if effective in {"edit", "refactor"}:
        return True
    lowered = query.lower()
    return any(term in lowered for term in ("fix", "modify", "patch", "rename", "update", "change"))


def _is_backend_path(path: str) -> bool:
    lowered = path.lower().replace("\\", "/")
    if lowered.startswith(_BACKEND_PATH_HINTS):
        return True
    tokens = _family_tokens(path) | {Path(path).stem.lower()}
    return bool(tokens & set(_BACKEND_FILE_HINTS))


def _query_shape(query: str, intent: str | None, explicit_paths: set[str]) -> str:
    terms = _query_terms(query)
    effective = _effective_intent(query, intent)
    lowered = query.lower()
    explicit_layers = {_layer_bucket(path) for path in explicit_paths}
    explicit_count = len(explicit_paths)

    has_frontend = any(layer == "frontend" for layer in explicit_layers) or "frontend/" in lowered
    has_backend = any(layer in {"backend", "api"} for layer in explicit_layers) or any(
        hint in lowered for hint in ("/api/", "app.py", "main.py", "backend")
    )
    has_chain_terms = bool(terms & _CHAIN_TERMS)

    if explicit_count >= 4 or (explicit_count >= 3 and has_chain_terms):
        return "multi_hop_chain"
    if has_frontend and has_backend:
        return "cross_layer_ui_api"
    if has_chain_terms and ("build" in terms or "planner" in terms or "stage" in terms):
        return "builder_orchestrator"

    backend_explicit = [path for path in explicit_paths if _is_backend_path(path)]
    if len(backend_explicit) >= 2 and effective in {"explore", "debug", "edit", "refactor"}:
        return "backend_config_pair"

    if explicit_count == 1:
        return "single_file"

    if explicit_count >= 2:
        families = {_candidate_family(path) for path in explicit_paths}
        if len(families) == 1:
            return "same_layer_pair"

    return "single_file"


def _is_generic_entrypoint(path: str) -> bool:
    normalized = path.lower().replace("\\", "/")
    candidate = Path(path)
    if normalized in _GENERIC_ENTRYPOINT_PATHS:
        return True
    if candidate.stem.lower() in _GENERIC_ENTRYPOINT_STEMS:
        return True
    return False


def _candidate_role(
    path: str | None,
    query: str,
    query_shape: str,
    explicit_targets: set[str],
    strong_paths: list[str],
) -> str:
    if not path:
        return "support_config"

    normalized = path.lower().replace("\\", "/")
    candidate = Path(path)
    stem = candidate.stem.lower()
    role = _file_role(path)

    if path in explicit_targets:
        return "explicit_target"
    if _is_generic_entrypoint(path):
        return "generic_entrypoint"
    if role in {"app", "main", "index", "router", "route", "entry", "command"}:
        return "caller_or_entry"

    if query_shape == "multi_hop_chain":
        tokens = _family_tokens(path)
        if tokens & {"plan", "build", "stage", "pipeline", "extract", "analyze"} and stem not in _GENERIC_ENTRYPOINT_STEMS:
            return "intermediate_pipeline"

    if _is_backend_path(path):
        for anchor in strong_paths:
            if not _is_backend_path(anchor):
                continue
            anchor_path = Path(anchor)
            if candidate.parent == anchor_path.parent and path != anchor:
                return "sibling_module"

    suffix = candidate.suffix.lower()
    if suffix in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".css", ".scss", ".sass", ".less", ".html"}:
        return "support_config"

    if "config" in normalized or "settings" in normalized or any(hint in normalized for hint in ("tailwind", "vite", "postcss", "vercel", "package.json")):
        return "support_config"

    return "sibling_module"


def _role_adjustment(role: str, query_shape: str, query: str, intent: str | None) -> float:
    effective = _effective_intent(query, intent)
    if role == "explicit_target":
        if _is_edit_like_query(query, intent):
            return 0.95
        return 0.55
    if role == "generic_entrypoint":
        if _is_edit_like_query(query, intent):
            return -0.4
        if query_shape in {"multi_hop_chain", "builder_orchestrator"}:
            return -0.12
        return -0.24
    if role == "sibling_module":
        if query_shape in {"backend_config_pair", "same_layer_pair"}:
            return 0.18
        return 0.08
    if role == "caller_or_entry":
        if query_shape in {"cross_layer_ui_api", "multi_hop_chain", "builder_orchestrator"}:
            return 0.16
        return 0.04
    if role == "intermediate_pipeline":
        if query_shape == "multi_hop_chain":
            return 0.3
        if query_shape == "builder_orchestrator":
            return 0.16
        return 0.08
    if role == "support_config":
        if effective == "debug":
            return -0.28
        if effective in {"edit", "refactor"}:
            return -0.16
        return -0.12
    return 0.0



def _subtree_locality_adjustment(path: str | None, explicit_targets: set[str], query_shape: str) -> float:
    if not path or not explicit_targets:
        return 0.0
    explicit_roots = {Path(item).parts[0].lower() for item in explicit_targets if Path(item).parts}
    explicit_families = {_candidate_family(item) for item in explicit_targets}
    candidate = Path(path)
    candidate_root = candidate.parts[0].lower() if candidate.parts else ""
    candidate_family = _candidate_family(path)

    if path in explicit_targets or candidate_family in explicit_families:
        return 0.12
    if query_shape in {"cross_layer_ui_api", "backend_config_pair"}:
        if candidate_root in explicit_roots:
            return 0.03
        return -0.08
    if len(explicit_roots) == 1:
        return -0.14 if candidate_root not in explicit_roots else 0.02
    return -0.04


def _support_config_penalty(path: str | None, role: str, explicit_targets: set[str]) -> float:
    if not path or not explicit_targets:
        return 0.0
    if role not in {"support_config", "general_doc", "operational_doc"}:
        return 0.0
    candidate_family = _candidate_family(path)
    explicit_families = {_candidate_family(item) for item in explicit_targets}
    if candidate_family in explicit_families:
        return -0.08
    return -0.26


def _promote_priority_first(
    ranked: list[RankedSnippet],
    explicit_priority_ids: set[str],
    linked_priority_ids: set[str],
    chain_priority_ids: set[str],
) -> list[RankedSnippet]:
    explicit_priority_ids = set(explicit_priority_ids)
    linked_priority_ids = set(linked_priority_ids)
    chain_priority_ids = set(chain_priority_ids)
    return sorted(
        ranked,
        key=lambda item: (
            0 if item.node_id in explicit_priority_ids else 1,
            0 if item.node_id in linked_priority_ids else 1,
            0 if item.node_id in chain_priority_ids else 1,
            0 if item.node_id.startswith("file:") else 1,
            -item.score,
            item.node_id,
        ),
    )

def _family_competition_adjustment(path: str | None, explicit_targets: set[str], query_shape: str) -> float:
    if not path or not explicit_targets:
        return 0.0
    explicit_families = {_candidate_family(item) for item in explicit_targets}
    family = _candidate_family(path)
    if family in explicit_families:
        return 0.16
    if query_shape in {"cross_layer_ui_api", "same_layer_pair", "backend_config_pair"}:
        return -0.06
    return -0.02

def _entrypoint_penalty(path: str, explicit_targets: set[str]) -> float:
    if not explicit_targets:
        return 0.0
    if not _is_generic_entrypoint(path):
        return 0.0

    candidate = Path(path)
    candidate_layer = _layer_bucket(path)
    candidate_family = _candidate_family(path)
    has_stronger_peer = any(
        target != path
        and (_layer_bucket(target) == candidate_layer or _candidate_family(target) == candidate_family)
        and not _is_generic_entrypoint(target)
        for target in explicit_targets
    )
    if has_stronger_peer:
        if candidate.stem.lower() in {"main", "app"}:
            return 0.34
        return 0.28
    return 0.0


def _explicit_priority_ids(file_text: dict[str, str], query: str, intent: str | None = None) -> set[str]:
    threshold = 0.5 if _is_edit_like_query(query, intent) else 0.75
    return {f"file:{path}" for score, path in _mentioned_file_paths(file_text, query) if score >= threshold}


def _layer_priority_ids(ranked: list[RankedSnippet], query: str, intent: str | None, explicit_priority_ids: set[str]) -> set[str]:
    if _effective_intent(query, intent) != "edit":
        return set()
    explicit_paths = [node_id[5:] for node_id in explicit_priority_ids if node_id.startswith("file:")]
    explicit_layers = {_layer_bucket(path) for path in explicit_paths}
    if len(explicit_layers) < 2:
        return set()

    best_by_layer: dict[str, tuple[float, str]] = {}
    for item in ranked:
        if not item.node_id.startswith("file:"):
            continue
        path = item.node_id[5:]
        if _classify_path(path) != "code":
            continue
        layer = _layer_bucket(path)
        if layer not in explicit_layers:
            continue
        current = best_by_layer.get(layer)
        score = item.score + _explicit_file_mention_score(path, query)
        if current is None or score > current[0] or (score == current[0] and item.node_id < current[1]):
            best_by_layer[layer] = (score, item.node_id)
    return {node_id for _, node_id in best_by_layer.values()}


def _family_tokens(path: str) -> set[str]:
    candidate = Path(path)
    tokens: set[str] = set()
    for part in candidate.parts:
        for token in re.split(r"[^a-zA-Z0-9_]+", part.lower()):
            for piece in token.split("_"):
                if len(piece) >= 3 and piece not in _COMMON_FAMILY_TOKENS:
                    tokens.add(piece)
    stem = candidate.stem.lower()
    for piece in stem.split("_"):
        if len(piece) >= 3 and piece not in _COMMON_FAMILY_TOKENS:
            tokens.add(piece)
    return tokens


def _path_match_score(path: str, query: str) -> float:
    terms = _query_terms(query)
    score = _explicit_file_mention_score(path, query)
    if not terms:
        return score
    lowered = path.lower()
    score = 0.0
    for term in terms:
        if term in lowered:
            score += 0.2
    parts = {part for part in re.split(r"[^a-zA-Z0-9_]+", lowered) if part}
    overlap = terms & parts
    if overlap:
        score += 0.15 * len(overlap)
    family_overlap = terms & _family_tokens(path)
    if family_overlap:
        score += 0.08 * len(family_overlap)
    if lowered.startswith("tests/") and "test" not in terms and "tests" not in terms:
        score -= 0.1
    return score


def _content_match_score(content: str, query: str) -> float:
    terms = _query_terms(query)
    if not terms:
        return 0.0
    lowered = content.lower()
    hits = sum(1 for term in terms if term in lowered)
    if hits == 0:
        return 0.0
    return min(0.35, hits * 0.07)


def _class_weight(path: str, query: str, intent: str | None) -> float:
    file_class = _classify_path(path)
    lowered_path = path.lower().replace("\\", "/")
    effective_intent = _effective_intent(query, intent)
    if effective_intent == "debug":
        if file_class == "code":
            return 0.4
        if "get-shit-done/" in lowered_path:
            return -0.45
        if file_class == "operational_doc":
            if "/templates/" in lowered_path:
                return -0.28
            return 0.12
        return -0.35
    if effective_intent == "explore":
        if file_class == "code":
            return 0.18
        if "get-shit-done/" in lowered_path:
            return -0.32
        if file_class == "operational_doc":
            if "/templates/" in lowered_path:
                return -0.2
            return 0.22
        return -0.05
    if effective_intent == "refactor":
        if file_class == "code":
            return 0.3
        if "get-shit-done/" in lowered_path:
            return -0.3
        if file_class == "operational_doc":
            if "/templates/" in lowered_path:
                return -0.18
            return 0.1
        return -0.15
    if file_class == "code":
        return 0.25
    if file_class == "operational_doc":
        return 0.1
    return -0.1


def _strong_path_matches(ranked: list[RankedSnippet], query: str, intent: str | None) -> list[str]:
    strong: list[str] = []
    for item in ranked:
        if item.node_id.startswith("file:"):
            path = item.node_id[5:]
        elif item.node_id.startswith(("function:", "class:")):
            path = item.node_id.split(":", 1)[1].split("::", 1)[0]
        else:
            continue
        strength = _path_match_score(path, query) + _class_weight(path, query, intent)
        if strength >= 0.55:
            strong.append(path)
    return strong[:8]


def _reference_tokens(path: str) -> set[str]:
    candidate = Path(path)
    dotted = ".".join(candidate.with_suffix("").parts)
    tokens = {candidate.stem.lower(), dotted.lower()}
    if candidate.parent.parts:
        tokens.add(f"{candidate.parent.name.lower()}.{candidate.stem.lower()}")
    return {token for token in tokens if token}


def _adjacency_boost(
    path: str,
    query: str,
    intent: str | None,
    strong_paths: list[str],
    file_text: dict[str, str],
) -> float:
    if not strong_paths:
        return 0.0
    current = Path(path)
    current_tokens = _family_tokens(path)
    current_class = _classify_path(path)
    terms = _query_terms(query)
    bonus = 0.0
    reference_tokens = _reference_tokens(path)
    for matched in strong_paths:
        if matched == path:
            continue
        matched_path = Path(matched)
        shared_tokens = current_tokens & _family_tokens(matched)
        if shared_tokens:
            bonus += min(0.24, 0.08 * len(shared_tokens))
        if current.parts and matched_path.parts and current.parts[0] == matched_path.parts[0]:
            bonus += 0.06
        if current.parent == matched_path.parent:
            bonus += 0.08
        if _is_backend_path(path) and _is_backend_path(matched) and current.parent == matched_path.parent and (terms & current_tokens):
            bonus += 0.18
        matched_text = file_text.get(matched, "").lower()
        if matched_text and any(token in matched_text for token in reference_tokens):
            bonus += 0.16
        if _is_system_query(query) and current_class == "code" and _classify_path(matched) == "code":
            if shared_tokens:
                bonus += 0.05
            if current.parent == matched_path.parent:
                bonus += 0.04
    return min(0.45, bonus)


def _support_role_bonus(path: str, query: str, strong_paths: list[str], file_text: dict[str, str]) -> float:
    current = Path(path)
    tokens = _family_tokens(path)
    score = 0.0
    if tokens & _SUPPORT_ROLE_TOKENS:
        score += 0.14
    if current.stem.lower() in _SUPPORT_ROLE_TOKENS:
        score += 0.12
    if _frontend_bias(query) and current.stem.lower() in {"app", "main", "index"}:
        score += 0.1
    for matched in strong_paths:
        matched_path = Path(matched)
        matched_text = file_text.get(matched, "").lower()
        if current == matched_path:
            continue
        if current.parts and matched_path.parts and current.parts[0] == matched_path.parts[0]:
            if tokens & _family_tokens(matched):
                score += 0.08
        if matched_text and any(token in matched_text for token in _reference_tokens(path)):
            score += 0.16
    return min(0.35, score)


def _mandatory_node_ids(
    ranked: list[RankedSnippet],
    query: str,
    intent: str | None,
    *,
    support_priority_ids: set[str] | None = None,
    explicit_priority_ids: set[str] | None = None,
) -> set[str]:
    mandatory: set[str] = set(support_priority_ids or set()) | set(explicit_priority_ids or set())
    support_enabled = _support_promotion_enabled(query, intent)
    for item in ranked:
        if not item.node_id.startswith("file:"):
            continue
        path = item.node_id[len("file:") :]
        file_class = _classify_path(path)
        if file_class == "general_doc" and _effective_intent(query, intent) == "debug":
            continue
        if file_class != "code" and item.node_id not in (explicit_priority_ids or set()):
            continue
        if _path_match_score(path, query) + _class_weight(path, query, intent) >= 0.45:
            mandatory.add(item.node_id)
            continue
        support_tokens = _family_tokens(path) | {Path(path).stem.lower()}
        if support_enabled and _classify_path(path) == "code" and support_tokens & _SUPPORT_ROLE_TOKENS and item.score >= 1.25:
            mandatory.add(item.node_id)
    return mandatory



def _linked_file_priority_ids(
    ranked: list[RankedSnippet],
    explicit_priority_ids: set[str],
    query_shape: str,
    query: str,
    intent: str | None,
) -> set[str]:
    if not explicit_priority_ids:
        return set()
    if not _is_edit_like_query(query, intent):
        return set()
    if query_shape not in {"same_layer_pair", "cross_layer_ui_api", "backend_config_pair", "builder_orchestrator"}:
        return set()

    keep = {
        item.node_id
        for item in sorted(ranked, key=lambda snippet: (-snippet.score, snippet.node_id))
        if item.node_id in explicit_priority_ids
    }
    return set(sorted(keep)[:3])


def _chain_quota_priority_ids(
    ranked: list[RankedSnippet],
    query: str,
    intent: str | None,
    explicit_targets: set[str],
) -> set[str]:
    query_shape = _query_shape(query, intent, explicit_targets)
    if query_shape not in {"multi_hop_chain", "builder_orchestrator"}:
        return set()

    file_candidates = [item for item in ranked if item.node_id.startswith("file:") and _classify_path(item.node_id[5:]) == "code"]
    if not file_candidates:
        return set()

    sorted_candidates = sorted(file_candidates, key=lambda item: (-item.score, item.node_id))
    caller = next(
        (
            item.node_id
            for item in sorted_candidates
            if _candidate_role(item.node_id[5:], query, query_shape, explicit_targets, []) in {"caller_or_entry", "generic_entrypoint"}
        ),
        None,
    )

    middle = next(
        (
            item.node_id
            for item in sorted_candidates
            if _candidate_role(item.node_id[5:], query, query_shape, explicit_targets, []) in {"intermediate_pipeline", "sibling_module"}
            and item.node_id != caller
        ),
        None,
    )

    downstream = next(
        (
            item.node_id
            for item in sorted_candidates
            if item.node_id != caller and item.node_id != middle and (
                item.node_id[5:] in explicit_targets or _candidate_role(item.node_id[5:], query, query_shape, explicit_targets, []) != "generic_entrypoint"
            )
        ),
        None,
    )

    return {node_id for node_id in (caller, middle, downstream) if node_id}

def _collect_repo_modules(repo_path: Path) -> tuple[list, dict, dict, dict, str, nx.DiGraph]:
    config = ScannerConfig.from_extensions(
        sorted(_ALL_CONTEXT_EXTENSIONS),
        include_hidden=False,
    )
    config.exclude_globs = _EXCLUDE_GLOBS
    manifest = scan_repository(repo_path, config=config)
    signature = _repo_signature(repo_path, manifest.files)

    cache_hit = _REPO_CACHE.get(signature)
    if cache_hit is not None:
        graph, file_text, function_snippets, class_snippets = cache_hit
        return [], file_text, function_snippets, class_snippets, signature, graph

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
        file_node_id = f"file:{file_rel}"
        graph.add_node(
            file_node_id,
            type="file",
            label=file_rel,
            path=file_rel,
            file_class=_classify_path(file_rel),
        )

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


def _boost_score(
    node_id: str,
    base_score: float,
    query: str,
    intent: str | None,
    strong_paths: list[str] | None = None,
    file_text: dict[str, str] | None = None,
) -> float:
    boosted = base_score
    strong_paths = strong_paths or []
    file_text = file_text or {}
    if node_id.startswith("file:"):
        path = node_id[len("file:") :]
        suffix = Path(path).suffix.lower()
        boosted += _path_match_score(path, query)
        boosted += _class_weight(path, query, intent)
        boosted += _adjacency_boost(path, query, intent, strong_paths, file_text)
        boosted += _support_role_bonus(path, query, strong_paths, file_text)
        if _frontend_bias(query) and suffix in _FRONTEND_EXTENSIONS:
            boosted += 0.2
        if suffix in {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx"}:
            boosted += 0.05
        return boosted

    if node_id.startswith(("function:", "class:")):
        file_path = node_id.split(":", 1)[1].split("::", 1)[0]
        boosted += _path_match_score(file_path, query)
        boosted += _class_weight(file_path, query, intent)
        boosted += _adjacency_boost(file_path, query, intent, strong_paths, file_text)
        boosted += _support_role_bonus(file_path, query, strong_paths, file_text)
        return boosted + 0.2

    return boosted


def _supplemental_file_snippets(
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    strong_paths: list[str],
    *,
    limit: int = 12,
) -> list[RankedSnippet]:
    supplemental: list[RankedSnippet] = []
    effective_intent = _effective_intent(query, intent)
    system_query = _is_system_query(query)
    for path, text in file_text.items():
        path_score = _path_match_score(path, query)
        content_score = _content_match_score(text[:4000], query)
        class_score = _class_weight(path, query, intent)
        adjacency = _adjacency_boost(path, query, intent, strong_paths, file_text)
        support_bonus = _support_role_bonus(path, query, strong_paths, file_text)
        total = path_score + content_score + class_score + adjacency + support_bonus
        if effective_intent == "debug" and _classify_path(path) == "general_doc":
            if total < 0.2:
                continue
        elif total <= 0.18:
            continue
        supplemental.append(
            RankedSnippet(
                node_id=f"file:{path}",
                content=_snippet_from_lines(text.splitlines(), max_lines=120),
                score=total,
            )
        )
    supplemental.sort(key=lambda item: (-item.score, item.node_id))
    if not system_query:
        return supplemental[:limit]

    selected: list[RankedSnippet] = []
    family_counts: dict[str, int] = {}
    for item in supplemental:
        family = Path(item.node_id[5:]).parts[0] if Path(item.node_id[5:]).parts else item.node_id
        if family_counts.get(family, 0) >= 3:
            continue
        selected.append(item)
        family_counts[family] = family_counts.get(family, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def _top_anchor_paths(ranked: list[RankedSnippet], *, limit: int = 6) -> list[str]:
    anchors: list[str] = []
    seen: set[str] = set()
    for item in sorted(ranked, key=lambda snippet: (-snippet.score, snippet.node_id)):
        if not item.node_id.startswith(("file:", "function:", "class:")):
            continue
        if item.node_id.startswith("file:"):
            path = item.node_id[5:]
        else:
            path = item.node_id.split(":", 1)[1].split("::", 1)[0]
        if _classify_path(path) != "code":
            continue
        if path in seen:
            continue
        anchors.append(path)
        seen.add(path)
        if len(anchors) >= limit:
            break
    return anchors


def _seed_anchor_paths(file_text: dict[str, str], query: str, intent: str | None, *, limit: int = 4) -> list[str]:
    seeded: list[tuple[float, str]] = []
    for path, text in file_text.items():
        if _classify_path(path) != "code":
            continue
        score = _path_match_score(path, query)
        score += _content_match_score(text[:2000], query)
        score += _class_weight(path, query, intent)
        score += _support_role_bonus(path, query, [], file_text)
        if score < 0.35:
            continue
        seeded.append((score, path))
    seeded.sort(key=lambda item: (-item[0], item[1]))
    return [path for _, path in seeded[:limit]]


def _repair_candidate_bonus(path: str, query: str, intent: str | None, anchor_paths: list[str], file_text: dict[str, str]) -> float:
    if not anchor_paths:
        return 0.0
    score = _support_role_bonus(path, query, anchor_paths, file_text)
    score += _adjacency_boost(path, query, intent, anchor_paths, file_text)
    tokens = _family_tokens(path)
    if _is_system_query(query) and tokens & _SUPPORT_ROLE_TOKENS:
        score += 0.08
    candidate = Path(path)
    for anchor in anchor_paths:
        anchor_path = Path(anchor)
        if candidate.parent == anchor_path.parent:
            score += 0.08
        if candidate.parts and anchor_path.parts and candidate.parts[0] == anchor_path.parts[0]:
            score += 0.05
    return min(0.55, score)


def _support_promotion_enabled(query: str, intent: str | None) -> bool:
    effective_intent = _effective_intent(query, intent)
    if effective_intent not in {"debug", "explore", "edit", "refactor"}:
        return False
    return bool(_query_terms(query) & _SUPPORT_PROMOTION_TERMS) or _is_system_query(query)


def _support_promotion_score(path: str, query: str, anchor_paths: list[str], file_text: dict[str, str]) -> float:
    if not anchor_paths:
        return 0.0
    candidate = Path(path)
    tokens = _family_tokens(path)
    score = 0.0
    if tokens & _SUPPORT_ROLE_TOKENS:
        score += 0.14
    if candidate.stem.lower() in _SUPPORT_ROLE_TOKENS:
        score += 0.12
    score += min(0.22, _path_match_score(path, query))

    for anchor in anchor_paths:
        anchor_path = Path(anchor)
        anchor_text = file_text.get(anchor, "").lower()
        if candidate.parent == anchor_path.parent:
            score += 0.16
        if candidate.parts and anchor_path.parts and candidate.parts[0] == anchor_path.parts[0]:
            score += 0.06
        if tokens & _family_tokens(anchor):
            score += 0.08
        if anchor_text and any(token in anchor_text for token in _reference_tokens(path)):
            score += 0.18
    return min(0.7, score)


def _promoted_support_file_snippets(
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    anchor_paths: list[str],
    existing_ids: set[str],
    *,
    limit: int = 2,
) -> list[RankedSnippet]:
    if not _support_promotion_enabled(query, intent):
        return []

    promoted: list[RankedSnippet] = []
    for path, text in file_text.items():
        node_id = f"file:{path}"
        if node_id in existing_ids:
            continue
        if _classify_path(path) != "code":
            continue
        promotion_score = _support_promotion_score(path, query, anchor_paths, file_text)
        if promotion_score < 0.38:
            continue
        total = promotion_score + _content_match_score(text[:3000], query)
        promoted.append(
            RankedSnippet(
                node_id=node_id,
                content=_snippet_from_lines(text.splitlines(), max_lines=120),
                score=total,
            )
        )

    promoted.sort(key=lambda item: (-item.score, item.node_id))
    return promoted[:limit]


def _support_priority_ids(ranked: list[RankedSnippet], query: str, intent: str | None) -> set[str]:
    if not _support_promotion_enabled(query, intent):
        return set()
    anchor_paths = _top_anchor_paths(ranked)
    if not anchor_paths:
        return set()

    candidates: list[tuple[float, str]] = []
    for item in ranked:
        if not item.node_id.startswith("file:"):
            continue
        path = item.node_id[5:]
        if _classify_path(path) != "code":
            continue
        support_score = _support_promotion_score(path, query, anchor_paths, {})
        support_tokens = _family_tokens(path) | {Path(path).stem.lower()}
        if not (support_tokens & _SUPPORT_ROLE_TOKENS):
            continue
        if support_score < 0.2 and item.score < 1.2:
            continue
        candidates.append((item.score + support_score, item.node_id))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return {node_id for _, node_id in candidates[:2]}


def _collapse_support_query_snippets(
    ranked: list[RankedSnippet],
    query: str,
    intent: str | None,
    file_text: dict[str, str],
) -> tuple[list[RankedSnippet], set[str]]:
    support_priority_ids = _support_priority_ids(ranked, query, intent)
    if not support_priority_ids:
        return ranked, set()

    retained_files = {node_id[5:] for node_id in support_priority_ids if node_id.startswith("file:")}
    filtered: list[RankedSnippet] = []
    for item in ranked:
        if item.node_id.startswith(("function:", "class:")):
            parent_path = item.node_id.split(":", 1)[1].split("::", 1)[0]
            if parent_path in retained_files:
                continue
        if item.node_id.startswith("file:"):
            path = item.node_id[5:]
            if path.endswith(".md") and retained_files:
                if _classify_path(path) != "operational_doc":
                    continue
        filtered.append(item)

    filtered.sort(
        key=lambda item: (
            0 if item.node_id in support_priority_ids else 1,
            0 if item.node_id.startswith("file:") else 1,
            -item.score,
            item.node_id,
        )
    )
    return filtered, support_priority_ids


def _repair_file_snippets(
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    ranked: list[RankedSnippet],
    existing_ids: set[str],
    *,
    limit: int = 4,
) -> list[RankedSnippet]:
    anchor_paths = _top_anchor_paths(ranked)
    if not anchor_paths:
        anchor_paths = _seed_anchor_paths(file_text, query, intent)
    if not anchor_paths:
        return []

    repair: list[RankedSnippet] = []
    promoted_ids: set[str] = set()
    for item in _promoted_support_file_snippets(file_text, query, intent, anchor_paths, existing_ids, limit=min(2, limit)):
        repair.append(item)
        promoted_ids.add(item.node_id)

    for path, text in file_text.items():
        node_id = f"file:{path}"
        if node_id in existing_ids or node_id in promoted_ids:
            continue
        if _classify_path(path) == "general_doc":
            continue
        base = _path_match_score(path, query) + _class_weight(path, query, intent)
        content = _content_match_score(text[:4000], query)
        repair_bonus = _repair_candidate_bonus(path, query, intent, anchor_paths, file_text)
        total = base + content + repair_bonus
        if total < 0.45:
            continue
        repair.append(
            RankedSnippet(
                node_id=node_id,
                content=_snippet_from_lines(text.splitlines(), max_lines=120),
                score=total,
            )
        )

    repair.sort(key=lambda item: (-item.score, item.node_id))
    return repair[:limit]


def _selected_anchor_paths(selected: tuple[RankedSnippet, ...], query: str, intent: str | None) -> list[str]:
    if not _support_promotion_enabled(query, intent):
        return []
    anchors: list[str] = []
    seen: set[str] = set()
    for item in selected:
        if item.node_id.startswith("file:"):
            path = item.node_id[5:]
        elif item.node_id.startswith(("function:", "class:")):
            path = item.node_id.split(":", 1)[1].split("::", 1)[0]
        else:
            continue
        if _classify_path(path) != "code":
            continue
        tokens = _family_tokens(path) | {Path(path).stem.lower()}
        if not (tokens & _SUPPORT_ROLE_TOKENS):
            continue
        if path in seen:
            continue
        anchors.append(path)
        seen.add(path)
    return anchors


def _reference_fallback_snippets(
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    selected: tuple[RankedSnippet, ...],
    existing_ids: set[str],
    *,
    limit: int = 2,
) -> list[RankedSnippet]:
    anchors = _selected_anchor_paths(selected, query, intent)
    if not anchors:
        return []

    recovered: list[RankedSnippet] = []
    for path, text in file_text.items():
        node_id = f"file:{path}"
        if node_id in existing_ids:
            continue
        if _classify_path(path) != "code":
            continue
        tokens = _family_tokens(path) | {Path(path).stem.lower()}
        if not (tokens & _SUPPORT_ROLE_TOKENS):
            continue
        candidate = Path(path)
        reference_hits = 0
        same_dir_hits = 0
        family_hits = 0
        for anchor in anchors:
            anchor_path = Path(anchor)
            anchor_text = file_text.get(anchor, "").lower()
            if candidate.parent == anchor_path.parent:
                same_dir_hits += 1
            if candidate.parts and anchor_path.parts and candidate.parts[0] == anchor_path.parts[0]:
                family_hits += 1
            if anchor_text and any(token in anchor_text for token in _reference_tokens(path)):
                reference_hits += 1
        if reference_hits == 0:
            continue
        total = (
            0.5 * reference_hits
            + 0.12 * same_dir_hits
            + 0.08 * family_hits
            + _path_match_score(path, query)
            + _content_match_score(text[:3000], query)
            + _class_weight(path, query, intent)
        )
        if total < 0.72:
            continue
        recovered.append(
            RankedSnippet(
                node_id=node_id,
                content=_snippet_from_lines(text.splitlines(), max_lines=120),
                score=total,
            )
        )

    recovered.sort(key=lambda item: (-item.score, item.node_id))
    return recovered[:limit]


def _apply_reference_fallback(
    ranked: list[RankedSnippet],
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    payload,
) -> tuple[list[RankedSnippet], set[str], str | None]:
    existing_ids = {item.node_id for item in ranked}
    recovered = _reference_fallback_snippets(file_text, query, intent, payload.snippets, existing_ids)
    if not recovered:
        return ranked, set(), None

    recovery_ids = {item.node_id for item in recovered}
    ranked.extend(recovered)
    ranked.sort(
        key=lambda item: (
            0 if item.node_id in recovery_ids else 1,
            0 if item.node_id.startswith("file:") else 1,
            -item.score,
            item.node_id,
        )
    )
    return ranked, recovery_ids, "reference_search"


@dataclass(frozen=True, slots=True)
class _ChannelCandidate:
    node_id: str
    channel: str
    score: float
    content: str
    rationale: str


@dataclass(frozen=True, slots=True)
class _AdaptiveCompanion:
    path: str
    score: float
    path_score: float
    same_family: bool
    role: str


def _node_file_path(node_id: str) -> str | None:
    if node_id.startswith("file:"):
        return node_id[5:]
    if node_id.startswith(("function:", "class:")):
        return node_id.split(":", 1)[1].split("::", 1)[0]
    return None


def _file_role(path: str | None) -> str:
    if not path:
        return "unknown"
    candidate = Path(path)
    stem = candidate.stem.lower()
    if stem in _SUPPORT_ROLE_TOKENS:
        return stem
    for token in sorted(_family_tokens(path)):
        if token in _SUPPORT_ROLE_TOKENS:
            return token
    file_class = _classify_path(path)
    if file_class == "operational_doc":
        return "operational_doc"
    if file_class == "general_doc":
        return "general_doc"
    return "module"


def _candidate_family(path: str | None) -> str:
    if not path:
        return "unknown"
    candidate = Path(path)
    if len(candidate.parts) >= 2:
        return "/".join(candidate.parts[:2])
    if candidate.parts:
        return candidate.parts[0]
    return candidate.stem


def _candidate_content(
    node_id: str,
    file_text: dict[str, str],
    function_snippets: dict[str, str],
    class_snippets: dict[str, str],
) -> str:
    snippet = function_snippets.get(node_id)
    if snippet is None:
        snippet = class_snippets.get(node_id)
    if snippet is None:
        file_path = _node_file_path(node_id)
        if file_path:
            text = file_text.get(file_path, "")
            if text:
                snippet = _snippet_from_lines(text.splitlines(), max_lines=120)
    return snippet or ""


def _query_variant(query: str, channel: str) -> str:
    if channel != "expand":
        return query
    expanded = sorted(_query_terms(query))
    return query if not expanded else f"{query} {' '.join(expanded)}"


def _file_channel_candidates(
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    *,
    channel: str,
    anchor_paths: list[str] | None = None,
    limit: int = 16,
) -> list[_ChannelCandidate]:
    if channel == "adj" and not anchor_paths:
        return []

    variant = _query_variant(query, channel)
    out: list[_ChannelCandidate] = []
    for path, text in file_text.items():
        file_class = _classify_path(path)
        if channel == "adj" and file_class != "code":
            continue
        path_score = _path_match_score(path, variant)
        content_score = _content_match_score(text[:4000], variant)
        class_score = _class_weight(path, query, intent)
        adjacency = 0.0
        support_bonus = 0.0
        threshold = 0.28

        if channel == "lex":
            threshold = 0.22
        elif channel == "expand":
            support_bonus = 0.6 * _support_role_bonus(path, variant, anchor_paths or [], file_text)
            threshold = 0.3
        elif channel == "adj":
            adjacency = _repair_candidate_bonus(path, query, intent, anchor_paths or [], file_text)
            support_bonus = _support_role_bonus(path, query, anchor_paths or [], file_text)
            threshold = 0.46

        total = path_score + content_score + class_score + adjacency + support_bonus
        if file_class == "general_doc" and _effective_intent(query, intent) == "debug":
            total -= 0.2
        if total < threshold:
            continue

        out.append(
            _ChannelCandidate(
                node_id=f"file:{path}",
                channel=channel,
                score=total,
                content=_snippet_from_lines(text.splitlines(), max_lines=120),
                rationale=f"path={path_score:.2f},content={content_score:.2f},adj={adjacency:.2f},support={support_bonus:.2f}",
            )
        )

    out.sort(key=lambda item: (-item.score, item.node_id))
    return out[:limit]


def _explicit_file_channel_candidates(
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    *,
    limit: int = 8,
) -> list[_ChannelCandidate]:
    out: list[_ChannelCandidate] = []
    for score, rel_path in _mentioned_file_paths(file_text, query)[:limit]:
        text = file_text.get(rel_path, "")
        if not text:
            continue
        out.append(
            _ChannelCandidate(
                node_id=f"file:{rel_path}",
                channel="target",
                score=score + 1.0,
                content=_snippet_from_lines(text.splitlines(), max_lines=220 if _is_edit_like_query(query, intent) else 120),
                rationale=f"explicit_file={score:.2f}",
            )
        )
    return out


def _vector_channel_candidates(
    graph: nx.DiGraph,
    query: str,
    file_text: dict[str, str],
    function_snippets: dict[str, str],
    class_snippets: dict[str, str],
    *,
    top_k: int,
) -> list[_ChannelCandidate]:
    out: list[_ChannelCandidate] = []
    for candidate in hybrid_retrieve(graph, query, top_k=top_k):
        content = _candidate_content(candidate.node_id, file_text, function_snippets, class_snippets)
        if not content:
            continue
        out.append(
            _ChannelCandidate(
                node_id=candidate.node_id,
                channel="vec",
                score=candidate.score,
                content=content,
                rationale=candidate.rationale,
            )
        )
    return out


def _fuse_context_channels(
    channel_map: dict[str, list[_ChannelCandidate]],
    query: str,
    intent: str | None,
    file_text: dict[str, str],
    *,
    explicit_targets: set[str] | None = None,
    query_shape: str | None = None,
    limit: int = 48,
) -> tuple[list[RankedSnippet], dict[str, dict[str, object]]]:
    channel_weights = {
        "target": 1.5,
        "lex": 1.0,
        "vec": 1.15,
        "expand": 0.9,
        "adj": 0.95,
        "fallback": 1.05,
    }
    merged: dict[str, dict[str, object]] = {}
    explicit_targets = explicit_targets or set()
    resolved_query_shape = query_shape or _query_shape(query, intent, explicit_targets)

    for channel_name in ("target", "lex", "vec", "expand", "adj", "fallback"):
        candidates = channel_map.get(channel_name, [])
        candidates = sorted(candidates, key=lambda item: (-item.score, item.node_id))
        for rank, item in enumerate(candidates, start=1):
            entry = merged.setdefault(
                item.node_id,
                {
                    "rrf": 0.0,
                    "best_score": item.score,
                    "content": item.content,
                    "channels": set(),
                    "rationales": [],
                },
            )
            entry["rrf"] = float(entry["rrf"]) + channel_weights.get(channel_name, 1.0) / (50.0 + rank)
            entry["best_score"] = max(float(entry["best_score"]), item.score)
            entry["content"] = entry["content"] or item.content
            cast_channels = entry["channels"]
            assert isinstance(cast_channels, set)
            cast_channels.add(channel_name)
            cast_rationales = entry["rationales"]
            assert isinstance(cast_rationales, list)
            cast_rationales.append(f"{channel_name}:{item.rationale}")

    preliminary = sorted(
        merged.items(),
        key=lambda pair: (-float(pair[1]["rrf"]), -float(pair[1]["best_score"]), pair[0]),
    )
    strong_paths: list[str] = []
    seen_paths: set[str] = set()
    for node_id, _ in preliminary:
        path = _node_file_path(node_id)
        if not path or _classify_path(path) != "code":
            continue
        if path in seen_paths:
            continue
        strong_paths.append(path)
        seen_paths.add(path)
        if len(strong_paths) >= 8:
            break

    ranked: list[RankedSnippet] = []
    attached: dict[str, dict[str, object]] = {}
    for node_id, entry in preliminary:
        path = _node_file_path(node_id)
        channels = tuple(sorted(entry["channels"]))
        final_score = float(entry["rrf"]) * 16.0 + _boost_score(
            node_id,
            float(entry["best_score"]),
            query,
            intent,
            strong_paths,
            file_text,
        )
        final_score += 0.05 * len(channels)
        if "target" in channels:
            final_score += 0.55
        if path:
            final_score -= _entrypoint_penalty(path, explicit_targets)
        if "lex" in channels and "vec" in channels:
            final_score += 0.18
        if "adj" in channels:
            final_score += 0.14
        if "expand" in channels:
            final_score += 0.08
        base_role = _file_role(path)
        candidate_role = "ranked"
        if explicit_targets:
            candidate_role = _candidate_role(path, query, resolved_query_shape, explicit_targets, strong_paths)
            final_score += _role_adjustment(candidate_role, resolved_query_shape, query, intent)
            final_score += _family_competition_adjustment(path, explicit_targets, resolved_query_shape)
            final_score += _subtree_locality_adjustment(path, explicit_targets, resolved_query_shape)
            final_score += _support_config_penalty(path, candidate_role, explicit_targets)
        if base_role in _SUPPORT_ROLE_TOKENS and _support_promotion_enabled(query, intent):
            final_score += 0.1

        ranked.append(
            RankedSnippet(
                node_id=node_id,
                content=str(entry["content"]),
                score=final_score,
            )
        )
        attached[node_id] = {
            "channels": list(channels[:4]),
            "family": _candidate_family(path),
            "file_role": base_role,
            "candidate_role": candidate_role,
            "query_shape": resolved_query_shape,
            "file_class": _classify_path(path) if path else "unknown",
            "why_included": "+".join(channels) if channels else "ranked",
        }

    ranked.sort(key=lambda item: (-item.score, item.node_id))
    return ranked[:limit], attached


def _selected_file_paths(selected: tuple[RankedSnippet, ...]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for item in selected:
        path = _node_file_path(item.node_id)
        if not path or path in seen:
            continue
        paths.append(path)
        seen.add(path)
    return paths


def _referenced_companion_paths(
    anchor_paths: list[str],
    file_text: dict[str, str],
    selected_paths: set[str],
) -> list[str]:
    referenced: list[str] = []
    for path in sorted(file_text):
        if path in selected_paths or _classify_path(path) != "code":
            continue
        tokens = _reference_tokens(path)
        for anchor in anchor_paths:
            anchor_text = file_text.get(anchor, "").lower()
            if anchor_text and any(token in anchor_text for token in tokens):
                referenced.append(path)
                break
    return referenced


def _context_fallback_reason(
    payload,
    query: str,
    intent: str | None,
    file_text: dict[str, str],
    attached: dict[str, dict[str, object]],
) -> str | None:
    selected_paths = _selected_file_paths(payload.snippets)
    code_paths = [path for path in selected_paths if _classify_path(path) == "code"]
    if not code_paths:
        return "insufficient_context_coverage"

    referenced_missing = _referenced_companion_paths(code_paths, file_text, set(selected_paths))
    if referenced_missing:
        return "support_family_missing"

    families = {_candidate_family(path) for path in code_paths}
    strong_files = 0
    for snippet in payload.snippets:
        meta = attached.get(snippet.node_id, {})
        channels = meta.get("channels", []) if isinstance(meta, dict) else []
        if len(channels) >= 2 and (_node_file_path(snippet.node_id) or "") in code_paths:
            strong_files += 1

    if _is_system_query(query) and (len(code_paths) < 2 or len(families) < 2):
        return "insufficient_context_coverage"
    if _support_promotion_enabled(query, intent) and strong_files < 2:
        return "low_context_confidence"
    return None


def _normal_search_fallback_snippets(
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    selected: tuple[RankedSnippet, ...],
    existing_ids: set[str],
    *,
    limit: int = 4,
) -> list[_ChannelCandidate]:
    selected_paths = _selected_file_paths(selected)
    anchors = [path for path in selected_paths if _classify_path(path) == "code"]
    referenced = set(_referenced_companion_paths(anchors, file_text, set(selected_paths)))

    out: list[_ChannelCandidate] = []
    for path, text in file_text.items():
        node_id = f"file:{path}"
        if node_id in existing_ids:
            continue
        file_class = _classify_path(path)
        if file_class == "general_doc" and _effective_intent(query, intent) == "debug":
            continue
        path_score = _path_match_score(path, query)
        content_score = _content_match_score(text[:5000], query)
        class_score = _class_weight(path, query, intent)
        adjacency = _adjacency_boost(path, query, intent, anchors, file_text)
        support_bonus = _support_role_bonus(path, query, anchors, file_text)
        total = path_score + content_score + class_score + adjacency + support_bonus
        if path in referenced:
            total += 0.75
        if total < 0.5:
            continue
        out.append(
            _ChannelCandidate(
                node_id=node_id,
                channel="fallback",
                score=total,
                content=_snippet_from_lines(text.splitlines(), max_lines=120),
                rationale=f"fallback:path={path_score:.2f},content={content_score:.2f},referenced={path in referenced}",
            )
        )

    out.sort(key=lambda item: (-item.score, item.node_id))
    return out[:limit]


def _apply_normal_search_fallback(
    ranked: list[RankedSnippet],
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    payload,
    attached: dict[str, dict[str, object]],
) -> tuple[list[RankedSnippet], dict[str, dict[str, object]], set[str], str | None, bool]:
    reason = _context_fallback_reason(payload, query, intent, file_text, attached)
    if not reason:
        return ranked, attached, set(), None, False

    existing_ids = {item.node_id for item in ranked}
    fallback_candidates = _normal_search_fallback_snippets(file_text, query, intent, payload.snippets, existing_ids)
    if not fallback_candidates:
        return ranked, attached, set(), reason, True

    fused_ranked, fused_attached = _fuse_context_channels({"fallback": fallback_candidates}, query, intent, file_text, limit=len(fallback_candidates))
    fallback_ids = {item.node_id for item in fused_ranked}
    for node_id, meta in fused_attached.items():
        attached[node_id] = meta
    ranked.extend(fused_ranked)
    ranked.sort(
        key=lambda item: (
            0 if item.node_id in fallback_ids else 1,
            0 if item.node_id.startswith("file:") else 1,
            -item.score,
            item.node_id,
        )
    )
    return ranked, attached, fallback_ids, reason, True



def _skeletonize_content(content: str, max_lines: int = 60) -> str:
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content

    signature_pattern = re.compile(r"^\s*(def\s+|class\s+|export\s+|function\s+|const\s+|let\s+|var\s+|@app\.route|if\s+__name__)", re.IGNORECASE)
    selected: list[str] = []
    for line in lines:
        if signature_pattern.search(line):
            selected.append(line)
        if len(selected) >= max_lines:
            break

    if len(selected) < min(20, max_lines):
        selected = lines[:max_lines]

    return "\n".join(selected).strip()


def _packaging_sets(
    ranked: list[RankedSnippet],
    attached: dict[str, dict[str, object]],
    *,
    explicit_priority_ids: set[str],
    linked_priority_ids: set[str],
    chain_priority_ids: set[str],
    mandatory_node_ids: set[str],
) -> tuple[set[str], set[str]]:
    pivot_ids = set(explicit_priority_ids) | set(linked_priority_ids) | set(chain_priority_ids)
    if not pivot_ids:
        for item in ranked:
            if item.node_id.startswith("file:"):
                pivot_ids.add(item.node_id)
            if len(pivot_ids) >= 2:
                break

    skeleton_ids: set[str] = set()
    for item in ranked:
        if not item.node_id.startswith("file:"):
            continue
        if item.node_id in pivot_ids or item.node_id in mandatory_node_ids:
            continue
        meta = attached.get(item.node_id, {})
        role = meta.get("candidate_role") if isinstance(meta, dict) else None
        if role in {"support_config", "sibling_module", "caller_or_entry", "generic_entrypoint"}:
            skeleton_ids.add(item.node_id)
    return pivot_ids, skeleton_ids


def _apply_packaging(
    ranked: list[RankedSnippet],
    pivot_ids: set[str],
    skeleton_ids: set[str],
    *,
    max_skeleton_lines: int = 60,
) -> list[RankedSnippet]:
    packed: list[RankedSnippet] = []
    for item in ranked:
        if item.node_id in skeleton_ids:
            packed.append(
                RankedSnippet(
                    node_id=item.node_id,
                    score=item.score,
                    content=_skeletonize_content(item.content, max_lines=max_skeleton_lines),
                )
            )
            continue
        packed.append(item)
    return packed

def run_context(path: str, query: str, budget: int | None, intent: str | None, top_k: int = 40) -> dict:
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
            node_id = f"class:{Path(cls.file).as_posix()}::{cls.name}"
            if snippet:
                class_snippets[node_id] = snippet

    explicit_priority_ids = _explicit_priority_ids(file_text, query, intent)
    explicit_target_paths = {node_id[5:] for node_id in explicit_priority_ids if node_id.startswith("file:")}
    query_shape = _query_shape(query, intent, explicit_target_paths)

    channels: dict[str, list[_ChannelCandidate]] = {
        "target": _explicit_file_channel_candidates(file_text, query, intent),
        "vec": _vector_channel_candidates(graph, query, file_text, function_snippets, class_snippets, top_k=top_k),
        "lex": _file_channel_candidates(file_text, query, intent, channel="lex", limit=18),
        "expand": _file_channel_candidates(file_text, query, intent, channel="expand", limit=14),
    }
    ranked, attached = _fuse_context_channels(
        channels,
        query,
        intent,
        file_text,
        explicit_targets=explicit_target_paths,
        query_shape=query_shape,
    )
    anchor_paths = _top_anchor_paths(ranked)
    channels["adj"] = _file_channel_candidates(file_text, query, intent, channel="adj", anchor_paths=anchor_paths, limit=10)
    ranked, attached = _fuse_context_channels(
        channels,
        query,
        intent,
        file_text,
        explicit_targets=explicit_target_paths,
        query_shape=query_shape,
    )

    ranked, support_priority_ids = _collapse_support_query_snippets(ranked, query, intent, file_text)
    explicit_priority_ids = {candidate.node_id for candidate in channels.get("target", [])}
    explicit_priority_ids |= _layer_priority_ids(ranked, query, intent, explicit_priority_ids)
    linked_priority_ids = _linked_file_priority_ids(ranked, explicit_priority_ids, query_shape, query, intent)
    chain_priority_ids = _chain_quota_priority_ids(ranked, query, intent, explicit_target_paths)
    ranked = _promote_priority_first(ranked, explicit_priority_ids, linked_priority_ids, chain_priority_ids)

    mandatory_node_ids = _mandatory_node_ids(
        ranked,
        query,
        intent,
        support_priority_ids=support_priority_ids | linked_priority_ids | chain_priority_ids,
        explicit_priority_ids=explicit_priority_ids | linked_priority_ids | chain_priority_ids,
    )

    pivot_node_ids, skeleton_node_ids = _packaging_sets(
        ranked,
        attached,
        explicit_priority_ids=explicit_priority_ids,
        linked_priority_ids=linked_priority_ids,
        chain_priority_ids=chain_priority_ids,
        mandatory_node_ids=mandatory_node_ids,
    )
    packed_ranked = _apply_packaging(ranked, pivot_node_ids, skeleton_node_ids)

    payload = build_context(
        query,
        packed_ranked,
        token_budget=budget,
        intent=intent,
        mandatory_node_ids=mandatory_node_ids,
    )

    ranked, attached, fallback_priority_ids, fallback_reason, fallback_search_used = _apply_normal_search_fallback(
        ranked,
        file_text,
        query,
        intent,
        payload,
        attached,
    )
    if fallback_priority_ids:
        combined_priority_ids = support_priority_ids | fallback_priority_ids | linked_priority_ids | chain_priority_ids
        ranked, support_priority_ids = _collapse_support_query_snippets(ranked, query, intent, file_text)
        combined_priority_ids |= support_priority_ids
        ranked = _promote_priority_first(ranked, explicit_priority_ids, linked_priority_ids, chain_priority_ids)
        mandatory_node_ids = _mandatory_node_ids(
            ranked,
            query,
            intent,
            support_priority_ids=combined_priority_ids,
            explicit_priority_ids=explicit_priority_ids | linked_priority_ids | chain_priority_ids,
        )
        pivot_node_ids, skeleton_node_ids = _packaging_sets(
            ranked,
            attached,
            explicit_priority_ids=explicit_priority_ids,
            linked_priority_ids=linked_priority_ids,
            chain_priority_ids=chain_priority_ids,
            mandatory_node_ids=mandatory_node_ids,
        )
        packed_ranked = _apply_packaging(ranked, pivot_node_ids, skeleton_node_ids)
        payload = build_context(
            query,
            packed_ranked,
            token_budget=budget,
            intent=intent,
            mandatory_node_ids=mandatory_node_ids,
        )

    snippets_out: list[dict[str, object]] = []
    for snippet in payload.snippets:
        base_meta = attached.get(
            snippet.node_id,
            {
                "channels": [],
                "family": _candidate_family(_node_file_path(snippet.node_id)),
                "file_role": _file_role(_node_file_path(snippet.node_id)),
                "candidate_role": "ranked",
                "query_shape": query_shape,
                "file_class": _classify_path(_node_file_path(snippet.node_id) or ""),
                "why_included": "selected",
            },
        )
        meta = dict(base_meta)
        if snippet.node_id in pivot_node_ids:
            meta["packaging_role"] = "pivot"
        elif snippet.node_id in skeleton_node_ids:
            meta["packaging_role"] = "adjacent_support"
        else:
            meta["packaging_role"] = "full"

        snippets_out.append(
            {
                "node_id": snippet.node_id,
                "score": snippet.score,
                "content": snippet.content,
                "attached_context": meta,
            }
        )

    return {
        "query": payload.query,
        "tokens": payload.total_tokens_estimate,
        "snippets": snippets_out,
        "fallback_search_used": fallback_search_used,
        "fallback_reason": fallback_reason,
    }

def _adaptive_companion_candidates(
    payload: dict,
    file_text: dict[str, str],
    query: str,
    intent: str | None,
) -> list[_AdaptiveCompanion]:
    selected_paths = _selected_file_paths(
        tuple(
            RankedSnippet(
                node_id=item["node_id"],
                content=item.get("content", ""),
                score=float(item.get("score", 0.0)),
            )
            for item in payload.get("snippets", [])
        )
    )
    selected_set = set(selected_paths)
    anchors = [path for path in selected_paths if _classify_path(path) == "code"]
    if not anchors:
        return []

    anchor_families = {_candidate_family(path) for path in anchors}
    candidates: list[_AdaptiveCompanion] = []
    for path in _referenced_companion_paths(anchors, file_text, selected_set):
        if _classify_path(path) != "code":
            continue
        text = file_text.get(path, "")
        path_score = _path_match_score(path, query)
        same_family = _candidate_family(path) in anchor_families
        role = _file_role(path)
        score = path_score
        score += _content_match_score(text[:4000], query)
        score += _class_weight(path, query, intent)
        score += _support_role_bonus(path, query, anchors, file_text)
        score += _adjacency_boost(path, query, intent, anchors, file_text)
        if same_family:
            score += 0.18
        if role in _SUPPORT_ROLE_TOKENS:
            score += 0.08
        candidates.append(
            _AdaptiveCompanion(
                path=path,
                score=score,
                path_score=path_score,
                same_family=same_family,
                role=role,
            )
        )

    candidates.sort(key=lambda item: (-item.score, item.path))
    return candidates


def _adaptive_missing_companions(
    payload: dict,
    file_text: dict[str, str],
    query: str,
    intent: str | None,
    *,
    limit: int = 1,
) -> list[str]:
    if payload.get("fallback_reason") != "support_family_missing":
        return []
    if not (_is_system_query(query) or _support_promotion_enabled(query, intent)):
        return []

    candidates = _adaptive_companion_candidates(payload, file_text, query, intent)
    filtered = [
        item for item in candidates
        if item.score >= 1.05 and (item.same_family or item.path_score >= 0.35 or item.role in _SUPPORT_ROLE_TOKENS)
    ]
    return [item.path for item in filtered[:limit]]


def _adaptive_replace_index(snippets: list[dict], family: str) -> int | None:
    candidates: list[tuple[float, int]] = []
    for idx, item in enumerate(snippets):
        attached = item.get("attached_context", {})
        if attached.get("why_included") == "adaptive_pin":
            continue
        if attached.get("family") != family:
            continue
        candidates.append((float(item.get("score", 0.0)), idx))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][1]


def run_context_adaptive(
    path: str,
    query: str,
    budget: int | None,
    intent: str | None,
    top_k: int = 40,
    *,
    completion_limit: int = 1,
) -> dict:
    payload = run_context(path, query, budget, intent, top_k=top_k)
    target = Path(path)
    repo_root = target if target.is_dir() else target.parent
    _, file_text, _, _, _, _ = _collect_repo_modules(repo_root)

    missing_paths = _adaptive_missing_companions(payload, file_text, query, intent, limit=completion_limit)
    if not missing_paths:
        payload["adaptive_completion_used"] = False
        payload["adaptive_completion_reason"] = None
        payload["adaptive_missing_files"] = []
        return payload

    remaining_budget = budget
    used_tokens = int(payload.get("tokens", 0))
    snippets = list(payload.get("snippets", []))
    existing_ids = {item["node_id"] for item in snippets}
    added: list[str] = []
    for rel_path in missing_paths:
        node_id = f"file:{rel_path}"
        if node_id in existing_ids:
            continue
        content = _snippet_from_lines(file_text.get(rel_path, "").splitlines(), max_lines=60)
        if not content:
            continue
        token_cost = estimate_tokens(content)
        family = _candidate_family(rel_path)
        replace_idx = _adaptive_replace_index(snippets, family)
        if replace_idx is not None:
            replaced = snippets.pop(replace_idx)
            used_tokens -= estimate_tokens(replaced.get("content", ""))
            existing_ids.discard(replaced["node_id"])
        if remaining_budget is not None and used_tokens + token_cost > remaining_budget:
            continue
        snippets.append(
            {
                "node_id": node_id,
                "score": 99.0,
                "content": content,
                "attached_context": {
                    "channels": ["adaptive_pin"],
                    "family": family,
                    "file_role": _file_role(rel_path),
                    "file_class": _classify_path(rel_path),
                    "why_included": "adaptive_pin",
                },
            }
        )
        used_tokens += token_cost
        existing_ids.add(node_id)
        added.append(rel_path)

    snippets.sort(key=lambda item: (0 if item.get("attached_context", {}).get("why_included") == "adaptive_pin" else 1, -float(item.get("score", 0.0)), item["node_id"]))
    payload["snippets"] = snippets
    payload["tokens"] = used_tokens
    payload["adaptive_completion_used"] = bool(added)
    payload["adaptive_completion_reason"] = "missing_referenced_companion" if added else None
    payload["adaptive_missing_files"] = added
    return payload



































