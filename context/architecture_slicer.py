"""Architecture-driven context slicing."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from llm_context.snippet_selector import estimate_tokens

from .architecture_index import load_architecture_index


_MISSING_RATIO_FALLBACK = 0.5
_STOPWORDS = {
    "for",
    "and",
    "the",
    "with",
    "from",
    "this",
    "that",
    "into",
    "onto",
    "over",
    "under",
    "fix",
    "add",
    "update",
    "refactor",
    "change",
    "when",
    "why",
    "how",
    "use",
    "using",
    "used",
    "make",
    "new",
}
_ARCH_KEYWORDS = {
    "fallback",
    "router",
    "routing",
    "context",
    "slicer",
    "architecture",
    "validation",
    "mode",
    "confidence",
}


@dataclass
class ArchitectureSliceResult:
    query: str
    snippets: list[dict]
    confidence: float
    matched_subsystems: list[dict]
    missing_files: list[str]
    error: str | None = None


def _tokenize(text: str) -> set[str]:
    tokens = []
    for raw in re.split(r"[\s_-]+", text.lower()):
        token = "".join(ch for ch in raw if ch.isalnum() or ch == "_")
        if len(token) >= 3:
            if token not in _STOPWORDS:
                tokens.append(token)
    return set(tokens)


def _subsystem_blob(subsystem: dict) -> str:
    parts = [subsystem.get("name", ""), subsystem.get("purpose", ""), subsystem.get("status", "")]
    for field in (
        subsystem.get("interfaces", []),
        subsystem.get("depends_on", []),
        subsystem.get("used_by", []),
        subsystem.get("failure_modes", []),
        subsystem.get("notes", []),
    ):
        if field:
            parts.extend(field)
    return " ".join(parts)


def _score_subsystem(subsystem: dict, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    blob = _subsystem_blob(subsystem).lower()
    matches = sum(1 for token in query_tokens if token in blob)
    return matches / max(len(query_tokens), 1)


def _snippet_from_lines(lines: list[str], max_lines: int) -> str:
    return "\n".join(lines[:max_lines]).strip()


def _collect_snippets(repo_path: Path, files: list[str], max_lines: int = 120) -> tuple[list[dict], list[str]]:
    snippets: list[dict] = []
    missing: list[str] = []
    for rel_path in files:
        file_path = repo_path / rel_path
        if not file_path.exists():
            missing.append(rel_path)
            continue
        try:
            content = file_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            missing.append(rel_path)
            continue
        snippet = _snippet_from_lines(content, max_lines=max_lines)
        if snippet:
            snippets.append(
                {
                    "node_id": f"file:{rel_path}",
                    "score": 1.0,
                    "content": snippet,
                }
            )
    return snippets, missing


def _validate_index(repo_path: Path, index_data: dict) -> tuple[list[dict], list[str], float]:
    missing: list[str] = []
    cleaned: list[dict] = []
    total = 0

    for subsystem in index_data.get("subsystems", []):
        key_files = subsystem.get("key_files", []) or []
        total += len(key_files)
        valid_files: list[str] = []
        for rel_path in key_files:
            if (repo_path / rel_path).exists():
                valid_files.append(rel_path)
            else:
                missing.append(rel_path)
        cleaned.append({**subsystem, "key_files": valid_files})

    if total == 0:
        return cleaned, missing, 0.0

    missing_ratio = len(missing) / total
    return cleaned, missing, missing_ratio


def _arch_query(query_tokens: set[str]) -> bool:
    return bool(query_tokens & _ARCH_KEYWORDS)


def _rank_core_files(core_files: list[str], query_tokens: set[str]) -> list[str]:
    weights = {
        "router": 3,
        "routing": 3,
        "fallback": 3,
        "architecture": 2,
        "slicer": 2,
        "validation": 2,
        "context": 1,
        "mode": 1,
        "confidence": 1,
    }
    ranked = []
    for path in core_files:
        lowered = path.lower()
        score = 0
        for key, weight in weights.items():
            if key in lowered:
                score += weight
        if query_tokens:
            score += sum(1 for token in query_tokens if token in lowered)
        ranked.append((score, path))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [path for score, path in ranked]


def _select_core_files(index_data: dict, query_tokens: set[str]) -> list[str]:
    core_files = index_data.get("core_infrastructure", []) or []
    return _rank_core_files(core_files, query_tokens)


def slice_with_architecture(repo_path: Path, query: str) -> ArchitectureSliceResult:
    index_path = repo_path / ".gcie" / "architecture_index.json"
    index_data = load_architecture_index(index_path)
    if index_data is None:
        return ArchitectureSliceResult(
            query=query,
            snippets=[],
            confidence=0.0,
            matched_subsystems=[],
            missing_files=[],
            error="index_missing",
        )

    subsystems, missing_files, missing_ratio = _validate_index(repo_path, index_data)
    if not subsystems:
        return ArchitectureSliceResult(
            query=query,
            snippets=[],
            confidence=0.0,
            matched_subsystems=[],
            missing_files=missing_files,
            error="no_subsystems",
        )

    if missing_ratio >= _MISSING_RATIO_FALLBACK and missing_files:
        return ArchitectureSliceResult(
            query=query,
            snippets=[],
            confidence=0.0,
            matched_subsystems=[],
            missing_files=missing_files,
            error="index_missing_files",
        )

    query_tokens = _tokenize(query)
    scored = []
    for subsystem in subsystems:
        score = _score_subsystem(subsystem, query_tokens)
        scored.append((score, subsystem))

    scored.sort(key=lambda item: item[0], reverse=True)
    matched = [(score, subsystem) for score, subsystem in scored if score > 0]

    if not matched:
        if _arch_query(query_tokens) and index_data.get("core_infrastructure"):
            core_files = _select_core_files(index_data, query_tokens)
            snippets, missing = _collect_snippets(repo_path, core_files)
            missing_files.extend(missing)
            return ArchitectureSliceResult(
                query=query,
                snippets=snippets,
                confidence=0.25,
                matched_subsystems=[],
                missing_files=missing_files,
                error=None,
            )
        return ArchitectureSliceResult(
            query=query,
            snippets=[],
            confidence=0.0,
            matched_subsystems=[],
            missing_files=missing_files,
            error="low_match",
        )

    top_score = matched[0][0]
    if missing_ratio > 0:
        top_score = max(top_score * (1.0 - missing_ratio), 0.0)

    selected_subsystems = [subsystem for score, subsystem in matched[:3]]
    selected_files: list[str] = []
    for subsystem in selected_subsystems:
        selected_files.extend(subsystem.get("key_files", []))

    include_core = False
    arch_query = _arch_query(query_tokens)
    if arch_query:
        include_core = True
    if arch_query and top_score <= 0.35:
        include_core = True
    if arch_query and len(selected_subsystems) <= 1:
        include_core = True

    core_files = _select_core_files(index_data, query_tokens)
    if include_core and core_files:
        selected_files = core_files + selected_files

    snippets, missing = _collect_snippets(repo_path, selected_files)
    missing_files.extend(missing)

    if include_core and core_files and not snippets:
        snippets, missing = _collect_snippets(repo_path, core_files)
        missing_files.extend(missing)

    return ArchitectureSliceResult(
        query=query,
        snippets=snippets,
        confidence=top_score,
        matched_subsystems=[
            {"name": subsystem.get("name", ""), "score": score}
            for score, subsystem in matched[:3]
        ],
        missing_files=missing_files,
        error=None,
    )


def trim_snippets_to_budget(snippets: list[dict], max_total: int) -> list[dict]:
    out: list[dict] = []
    used = 0
    for item in snippets:
        tokens = estimate_tokens(item.get("content", ""))
        if used + tokens > max_total:
            continue
        out.append(item)
        used += tokens
    return out









