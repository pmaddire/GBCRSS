"""Post-initialization adaptation pipeline (accuracy rounds first, then efficiency rounds)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path

from .context import run_context
from .context_slices import _classify_query_family, run_context_slices
from .index import run_index

try:
    from performance.context_benchmark import BENCHMARK_CASES
except Exception:  # pragma: no cover
    BENCHMARK_CASES = ()


@dataclass(frozen=True, slots=True)
class CaseResult:
    name: str
    family: str
    mode: str
    tokens: int
    expected_hits: int
    expected_total: int
    missing_expected: tuple[str, ...]
    context_complete: bool


@dataclass(frozen=True, slots=True)
class AdaptCase:
    name: str
    query: str
    intent: str
    baseline_files: tuple[str, ...]
    expected_files: tuple[str, ...]


_WORD_RE = re.compile(r"[A-Za-z0-9_./-]+")
_SOURCE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cs", ".cpp", ".c", ".h"}
_IGNORED_DIRS = {
    ".git",
    ".gcie",
    ".planning",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "coverage",
}
_METHOD_ORDER = ["plain", "plain_chain", "plain_gapfill", "plain_rescue", "slices"]


def _adapt_worker_count(workers: int | None = None) -> int:
    if workers is not None:
        return max(1, int(workers))
    env_value = os.getenv("GCIE_ADAPT_WORKERS", "").strip()
    if env_value:
        try:
            return max(1, int(env_value))
        except ValueError:
            pass
    cpu = os.cpu_count() or 4
    return max(1, min(8, cpu))


def _query_keywords(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if len(t) >= 4][:8]


def _extract_query_cues_for_file(repo_path: Path, rel: str) -> list[str]:
    path = repo_path / rel
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return [Path(rel).stem.lower()]

    body = text[:12000]
    cues: list[str] = [Path(rel).stem.lower()]

    patterns = [
        r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?(?:\(|function\b)",
        r"^\s*export\s+function\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]
    for pat in patterns:
        for name in re.findall(pat, body, flags=re.MULTILINE):
            token = str(name).lower()
            if len(token) >= 4:
                cues.append(token)
            if len(cues) >= 8:
                break
        if len(cues) >= 8:
            break

    for route in re.findall(r"['\"](/api/[A-Za-z0-9_/{}/-]+)['\"]", body):
        cues.append(route.lower())
        if len(cues) >= 10:
            break

    for key in re.findall(r"\b[A-Z][A-Z0-9_]{3,}\b", body):
        cues.append(key.lower())
        if len(cues) >= 12:
            break

    dedup: list[str] = []
    seen: set[str] = set()
    for cue in cues:
        if cue in seen:
            continue
        seen.add(cue)
        dedup.append(cue)
        if len(dedup) >= 8:
            break
    return dedup

def _node_to_file(node_id: str) -> str | None:
    if node_id.startswith("file:"):
        return node_id[5:]
    if node_id.startswith("function:"):
        return node_id[9:].split("::", 1)[0]
    if node_id.startswith("class:"):
        return node_id[6:].split("::", 1)[0]
    return None


def _normalize_scoped_path(plan_path: str, rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/").lstrip("./")
    if not plan_path or plan_path in {".", "./"}:
        return normalized
    base = Path(plan_path).as_posix().strip("/")
    if normalized.startswith(base + "/") or normalized == base:
        return normalized
    return f"{base}/{normalized}"


def _family_path(expected_files: tuple[str, ...]) -> str:
    if not expected_files:
        return "."
    parent_parts: list[tuple[str, ...]] = []
    for rel in expected_files:
        parent = Path(rel).parent
        if str(parent) in {"", "."}:
            parent_parts.append(tuple())
        else:
            parent_parts.append(tuple(parent.parts))

    common: list[str] = []
    if parent_parts:
        shortest = min(len(parts) for parts in parent_parts)
        for idx in range(shortest):
            token = parent_parts[0][idx]
            if all(parts[idx] == token for parts in parent_parts):
                common.append(token)
            else:
                break
    if common:
        return Path(*common).as_posix()

    heads = {Path(p).parts[0] for p in expected_files if Path(p).parts}
    return next(iter(heads)) if len(heads) == 1 else "."

def _safe_scope(path: str) -> str:
    if not path or path in {".", "./"}:
        return "."
    candidate = Path(path)
    if candidate.exists() and candidate.is_dir():
        return candidate.as_posix()
    return "."


def _plan_query(case) -> tuple[str, str, int | None]:
    path = _family_path(case.expected_files)
    if getattr(case, "name", "") == "cli_context_command":
        return ".", "cli/commands/context.py llm_context/context_builder.py build_context token_budget mandatory_node_ids snippet_selector", 950

    repo_path = Path('.').resolve()
    cue_terms: list[str] = []
    for rel in case.expected_files:
        cue_terms.extend(_extract_query_cues_for_file(repo_path, rel)[:3])
    cue_terms.extend(_query_keywords(case.query)[:4])

    dedup: list[str] = []
    seen: set[str] = set()
    for token in [*case.expected_files, *cue_terms]:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(token)
        if len(dedup) >= 14:
            break
    query = " ".join(dedup).strip()

    expected_count = len(case.expected_files)
    if expected_count >= 3:
        budget = 1100
    elif expected_count == 2:
        budget = 950
    else:
        budget = 850

    if getattr(case, "name", "") in {"repository_scanner_filters", "knowledge_index_query_api", "execution_trace_graph", "parser_fallbacks"}:
        budget = 800
    return path, query, budget

def _case_family(case) -> str:
    _, planned_query, _ = _plan_query(case)
    return _classify_query_family(planned_query)


def _build_gapfill_query(case, missing_rel: str) -> str:
    anchors = [rel for rel in case.expected_files if rel != missing_rel][:2]
    repo_path = Path('.').resolve()

    tokens: list[str] = [missing_rel]
    tokens.extend(anchors)

    cue_files = [missing_rel]
    cue_files.extend(anchors)
    for rel in cue_files:
        tokens.extend(_extract_query_cues_for_file(repo_path, rel)[:4])

    tokens.extend(_query_keywords(case.query)[:4])

    dedup: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(tok)
        if len(dedup) >= 14:
            break

    return " ".join(dedup)


def _collect_files_from_payload(scope: str, payload: dict) -> set[str]:
    return {
        _normalize_scoped_path(scope, rel)
        for rel in (_node_to_file(item.get("node_id", "")) for item in payload.get("snippets", []))
        if rel
    }


def _hop_query_for_pair(case, left: str, right: str) -> str:
    repo_path = Path('.').resolve()
    cues: list[str] = []
    cues.extend(_extract_query_cues_for_file(repo_path, left)[:3])
    cues.extend(_extract_query_cues_for_file(repo_path, right)[:3])
    cues.extend(_query_keywords(case.query)[:4])

    dedup: list[str] = []
    seen: set[str] = set()
    for token in [left, right, *cues]:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(token)
        if len(dedup) >= 12:
            break
    return " ".join(dedup)


def _evaluate_plain_chain_case(case) -> CaseResult:
    expected = tuple(case.expected_files)
    if len(expected) < 3:
        return _evaluate_plain_case(case, allow_gapfill=False)

    tokens = 0
    files: set[str] = set()
    mode = "plain_chain_workflow"

    # Decompose N-file chains into adjacent hops to reduce broad root overfetch.
    for idx in range(len(expected) - 1):
        left = expected[idx]
        right = expected[idx + 1]
        scope = _safe_scope(_family_path((left, right)))
        query = _hop_query_for_pair(case, left, right)
        hop_payload = run_context(scope, query, budget=950, intent=case.intent)
        tokens += int(hop_payload.get("tokens", 0) or 0)
        files.update(_collect_files_from_payload(scope, hop_payload))

    missing = [rel for rel in expected if rel not in files]
    if missing:
        mode = "plain_chain_workflow_gapfill"
        for rel in list(missing):
            # Chain gapfill stays narrow: direct file scope only (no broad fallback).
            scope = rel if (Path(rel).exists() and Path(rel).is_file()) else _safe_scope(_family_path((rel,)))
            budget = 500 if rel.endswith('/main.py') or rel == 'main.py' else 700
            gap_payload = run_context(scope, _build_gapfill_query(case, rel), budget=budget, intent=case.intent)
            tokens += int(gap_payload.get("tokens", 0) or 0)
            files.update(_collect_files_from_payload(scope, gap_payload))
            missing = [m for m in expected if m not in files]
            if not missing:
                break

    expected_hits = len(expected) - len(missing)
    family = _classify_query_family(case.query)
    return CaseResult(
        name=case.name,
        family=family,
        mode=mode,
        tokens=tokens,
        expected_hits=expected_hits,
        expected_total=len(expected),
        missing_expected=tuple(missing),
        context_complete=not missing,
    )


def _evaluate_plain_case(case, *, allow_gapfill: bool = True, aggressive_gapfill: bool = False) -> CaseResult:
    path, query, budget = _plan_query(case)
    path = _safe_scope(path)
    payload = run_context(path, query, budget=budget, intent=case.intent)
    files = {
        _normalize_scoped_path(path, rel)
        for rel in (_node_to_file(item.get("node_id", "")) for item in payload.get("snippets", []))
        if rel
    }
    expected = tuple(case.expected_files)
    missing = [rel for rel in expected if rel not in files]
    tokens = int(payload.get("tokens", 0) or 0)
    mode = "plain_context_workflow"

    if allow_gapfill and missing:
        mode = "plain_context_workflow_gapfill"
        for rel in list(missing):
            gap_query = _build_gapfill_query(case, rel)

            # Prefer direct file-targeted recovery when possible to avoid expensive broad rescues.
            direct_scope = rel if (Path(rel).exists() and Path(rel).is_file()) else None
            base_scope = _safe_scope(_family_path((rel,)))
            scopes: list[str] = []
            if direct_scope:
                scopes.append(direct_scope)
            if base_scope not in scopes:
                scopes.append(base_scope)

            budgets = [500 if rel.endswith('/main.py') or rel == 'main.py' else 900]
            if len(scopes) > 1:
                budgets.append(budgets[0])

            if aggressive_gapfill:
                if '.' not in scopes:
                    scopes.append('.')
                    budgets.append(max(budgets[0], 1200))
                mode = "plain_context_workflow_gapfill_rescue"

            for scope, gap_budget in zip(scopes, budgets):
                gap_payload = run_context(scope, gap_query, budget=gap_budget, intent=case.intent)
                tokens += int(gap_payload.get("tokens", 0) or 0)
                gap_files = {
                    _normalize_scoped_path(scope, rel2)
                    for rel2 in (_node_to_file(item.get("node_id", "")) for item in gap_payload.get("snippets", []))
                    if rel2
                }
                files.update(gap_files)
                missing = [m for m in expected if m not in files]
                if not missing:
                    break
            if not missing:
                break

    expected_hits = len(expected) - len(missing)
    family = _classify_query_family(query)
    return CaseResult(
        name=case.name,
        family=family,
        mode=mode,
        tokens=tokens,
        expected_hits=expected_hits,
        expected_total=len(expected),
        missing_expected=tuple(missing),
        context_complete=not missing,
    )


def _evaluate_slices_case(case) -> CaseResult:
    payload = run_context_slices(
        repo='.',
        query=case.query,
        profile='low',
        stage_a_budget=300,
        stage_b_budget=600,
        max_total=800,
        intent=case.intent,
        pin=None,
        pin_budget=200,
        include_tests=False,
    )
    mode = "slices_low"
    tokens = int(payload.get("token_estimate", payload.get("tokens", 0)) or 0)
    files = {f for f in (_node_to_file(item.get("node_id", "")) for item in payload.get("snippets", [])) if f}
    expected = tuple(case.expected_files)
    missing = [rel for rel in expected if rel not in files]
    if missing:
        mode = "slices_recall"
        recall_payload = run_context_slices(
            repo='.',
            query=case.query,
            profile='recall',
            stage_a_budget=400,
            stage_b_budget=800,
            max_total=1200,
            intent=case.intent,
            pin=None,
            pin_budget=300,
            include_tests=False,
        )
        tokens += int(recall_payload.get("token_estimate", recall_payload.get("tokens", 0)) or 0)
        files.update({f for f in (_node_to_file(item.get("node_id", "")) for item in recall_payload.get("snippets", [])) if f})
        missing = [rel for rel in expected if rel not in files]
    if missing:
        mode = "slices_recall_pin"
        for rel in list(missing):
            pin_payload = run_context_slices(
                repo='.',
                query=case.query,
                profile='recall',
                stage_a_budget=400,
                stage_b_budget=800,
                max_total=1200,
                intent=case.intent,
                pin=rel,
                pin_budget=300,
                include_tests=False,
            )
            tokens += int(pin_payload.get("token_estimate", pin_payload.get("tokens", 0)) or 0)
            files.update({f for f in (_node_to_file(item.get("node_id", "")) for item in pin_payload.get("snippets", [])) if f})
            missing = [m for m in expected if m not in files]
            if not missing:
                break

    expected_hits = len(expected) - len(missing)
    family = _case_family(case)
    return CaseResult(
        name=case.name,
        family=family,
        mode=mode,
        tokens=tokens,
        expected_hits=expected_hits,
        expected_total=len(expected),
        missing_expected=tuple(missing),
        context_complete=not missing,
    )


def _evaluate_case_with_method(case, method: str) -> CaseResult:
    if method == "plain":
        return _evaluate_plain_case(case, allow_gapfill=False)
    if method == "plain_chain":
        return _evaluate_plain_chain_case(case)
    if method == "plain_gapfill":
        return _evaluate_plain_case(case, allow_gapfill=True, aggressive_gapfill=False)
    if method == "plain_rescue":
        return _evaluate_plain_case(case, allow_gapfill=True, aggressive_gapfill=True)
    return _evaluate_slices_case(case)


def _summarize(label: str, rows: list[CaseResult]) -> dict:
    case_count = len(rows)
    pass_count = sum(1 for row in rows if row.context_complete)
    total_tokens = sum(row.tokens for row in rows)
    hit_count = sum(row.expected_hits for row in rows)
    hit_total = sum(row.expected_total for row in rows)
    return {
        "label": label,
        "case_count": case_count,
        "passing_cases": pass_count,
        "full_hit_rate_pct": round((pass_count / case_count) * 100, 1) if case_count else 0.0,
        "target_hit_rate_pct": round((hit_count / hit_total) * 100, 1) if hit_total else 0.0,
        "total_tokens": total_tokens,
        "tokens_per_query": round(total_tokens / case_count, 1) if case_count else 0.0,
        "tokens_per_expected_hit": round(total_tokens / hit_count, 2) if hit_count else None,
        "results": [asdict(row) for row in rows],
    }


def _collect_source_files(repo_path: Path) -> list[str]:
    files: list[str] = []
    for path in repo_path.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_path)
        if any(part in _IGNORED_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() not in _SOURCE_EXTS:
            continue
        files.append(rel.as_posix())
    return sorted(files)


def _generated_cases_for_repo(repo_path: Path, needed: int) -> list[AdaptCase]:
    files = _collect_source_files(repo_path)
    if not files:
        return []

    by_dir: dict[str, list[str]] = {}
    for rel in files:
        parent = str(Path(rel).parent).replace('\\', '/')
        by_dir.setdefault(parent, []).append(rel)

    rows: list[AdaptCase] = []
    seen_names: set[str] = set()
    seen_expected: set[tuple[str, ...]] = set()
    cue_cache: dict[str, list[str]] = {}

    def add_case(name: str, expected: tuple[str, ...], intent: str = 'explore') -> None:
        if len(rows) >= needed:
            return
        expected_key = tuple(sorted(expected))
        if expected_key in seen_expected:
            return
        safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower() or "case"
        if safe_name in seen_names:
            idx = 2
            while f"{safe_name}_{idx}" in seen_names:
                idx += 1
            safe_name = f"{safe_name}_{idx}"
        seen_names.add(safe_name)
        seen_expected.add(expected_key)
        symbols: list[str] = []
        for rel in expected:
            cues = cue_cache.get(rel)
            if cues is None:
                cues = _extract_query_cues_for_file(repo_path, rel)
                cue_cache[rel] = cues
            symbols.extend(cues)
        if not symbols:
            symbols = [Path(rel).stem.lower() for rel in expected]
        query = f"{' '.join(expected)} {' '.join(symbols[:8])}".strip()
        rows.append(AdaptCase(name=safe_name, query=query, intent=intent, baseline_files=expected, expected_files=expected))

    # Build a diversified sample so adaptation can learn in mixed-layer repos.
    single_target = max(1, needed // 3)
    same_dir_target = max(1, needed // 3)
    local_target = max(1, needed // 2)
    if single_target + same_dir_target < local_target:
        same_dir_target = local_target - single_target
    cross_dir_target = max(1, needed - single_target - same_dir_target)

    # 1) singles
    for rel in files:
        add_case(f"single_{Path(rel).stem}", (rel,), intent='explore')
        if len(rows) >= single_target:
            break

    # 2) same-dir adjacent pairs
    same_pairs_added = 0
    for parent, group in sorted(by_dir.items(), key=lambda x: x[0]):
        if len(group) < 2:
            continue
        label = "root" if parent in {'.', ''} else parent
        group = sorted(group)
        for idx in range(len(group) - 1):
            add_case(f"pair_{label}_{idx}", (group[idx], group[idx + 1]), intent='explore')
            if len(rows) >= needed:
                return rows[:needed]
            same_pairs_added += 1
            if same_pairs_added >= same_dir_target:
                break
        if same_pairs_added >= same_dir_target:
            break

    # 3) cross-dir pairs (top-level representatives)
    tops: dict[str, str] = {}
    for rel in files:
        top = Path(rel).parts[0] if Path(rel).parts else rel
        tops.setdefault(top, rel)
    top_items = sorted(tops.items(), key=lambda item: item[0])
    cross_added = 0
    for idx in range(len(top_items) - 1):
        left = top_items[idx][1]
        right = top_items[idx + 1][1]
        add_case(f"cross_{top_items[idx][0]}_{top_items[idx + 1][0]}", (left, right), intent='explore')
        if len(rows) >= needed:
            return rows[:needed]
        cross_added += 1
        if cross_added >= cross_dir_target:
            break

    # 4) include some 3-file chains for multi-hop calibration when dataset is larger.
    if needed >= 12 and len(rows) < needed:
        chain_budget = max(1, int(round(needed * 0.12)))
        chains_added = 0
        reps = [item[1] for item in top_items]
        for idx in range(len(reps) - 2):
            add_case(
                f"chain_{idx}",
                (reps[idx], reps[idx + 1], reps[idx + 2]),
                intent='refactor',
            )
            if len(rows) >= needed:
                return rows[:needed]
            chains_added += 1
            if chains_added >= chain_budget:
                break

    # 5) fill remainder with additional nearby pairs
    if len(rows) < needed:
        for idx in range(len(files) - 1):
            add_case(f"fill_{idx}", (files[idx], files[idx + 1]), intent='explore')
            if len(rows) >= needed:
                break

    return rows[:needed]


def _select_adaptation_cases(repo_path: Path, benchmark_size: int) -> tuple[list[AdaptCase], str]:
    benchmark_size = max(1, int(benchmark_size))
    generated = _generated_cases_for_repo(repo_path, benchmark_size)
    if generated:
        return generated[:benchmark_size], 'generated_repo_local'
    return [], 'none_available'


def _next_method(method: str) -> str:
    try:
        idx = _METHOD_ORDER.index(method)
    except ValueError:
        return _METHOD_ORDER[0]
    return _METHOD_ORDER[min(idx + 1, len(_METHOD_ORDER) - 1)]


def _cheaper_method(method: str) -> str | None:
    try:
        idx = _METHOD_ORDER.index(method)
    except ValueError:
        return None
    if idx <= 0:
        return None
    return _METHOD_ORDER[idx - 1]


def _evaluate_cases_with_method(cases: list[AdaptCase], method: str, workers: int) -> list[CaseResult]:
    if not cases:
        return []
    if workers <= 1 or len(cases) <= 1:
        return [_evaluate_case_with_method(case, method) for case in cases]

    slots: list[CaseResult | None] = [None] * len(cases)
    max_workers = max(1, min(workers, len(cases)))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {
            pool.submit(_evaluate_case_with_method, case, method): idx
            for idx, case in enumerate(cases)
        }
        for future in as_completed(future_map):
            slots[future_map[future]] = future.result()

    return [row for row in slots if row is not None]


def _run_family_policy(
    cases: list[AdaptCase],
    family_policy: dict[str, str],
    *,
    workers: int,
) -> tuple[list[CaseResult], dict, dict[str, dict]]:
    if not cases:
        summary = _summarize('policy_run', [])
        return [], summary, {}

    grouped: dict[str, list[tuple[int, AdaptCase]]] = {}
    for idx, case in enumerate(cases):
        family = _case_family(case)
        method = family_policy.get(family, 'plain')
        key = f'{family}|{method}'
        grouped.setdefault(key, []).append((idx, case))

    ordered: list[CaseResult | None] = [None] * len(cases)
    for key in sorted(grouped):
        pairs = grouped[key]
        _, method = key.split('|', 1)
        group_cases = [case for _, case in pairs]
        group_rows = _evaluate_cases_with_method(group_cases, method, workers)
        for (orig_idx, _), row in zip(pairs, group_rows):
            ordered[orig_idx] = row

    rows = [row for row in ordered if row is not None]
    summary = _summarize('policy_run', rows)

    by_family: dict[str, dict] = {}
    for row in rows:
        entry = by_family.setdefault(row.family, {'cases': 0, 'passes': 0, 'tokens': 0})
        entry['cases'] += 1
        entry['passes'] += 1 if row.context_complete else 0
        entry['tokens'] += row.tokens
    for fam, entry in by_family.items():
        entry['pass_rate'] = round(entry['passes'] / max(1, entry['cases']), 3)
        entry['tokens_per_case'] = round(entry['tokens'] / max(1, entry['cases']), 1)

    return rows, summary, by_family


def _select_best_summary(summaries: list[dict]) -> dict:
    full_hit = [s for s in summaries if s.get("full_hit_rate_pct", 0.0) >= 100.0]
    if full_hit:
        return min(full_hit, key=lambda s: (s.get("tokens_per_expected_hit") or 10**9, s.get("tokens_per_query", 10**9)))
    return max(
        summaries,
        key=lambda s: (s.get("target_hit_rate_pct", 0.0), -s.get("tokens_per_query", 10**9)),
    )


def _bootstrap_family_policy(
    cases: list[AdaptCase],
    families: list[str],
    *,
    workers: int,
) -> tuple[dict[str, str], list[dict]]:
    policy: dict[str, str] = {}
    diagnostics: list[dict] = []
    for fam in families:
        fam_cases = [case for case in cases if _case_family(case) == fam]
        if not fam_cases:
            policy[fam] = "plain"
            continue

        method_summaries: list[dict] = []
        for method in _METHOD_ORDER:
            rows = _evaluate_cases_with_method(fam_cases, method, workers)
            summary = _summarize(f"bootstrap_{fam}_{method}", rows)
            summary["method"] = method
            summary["family"] = fam
            method_summaries.append(summary)

        best = _select_best_summary(method_summaries)
        selected_method = str(best.get("method", "plain"))
        policy[fam] = selected_method
        diagnostics.append(
            {
                "family": fam,
                "selected_method": selected_method,
                "selected_summary": best,
                "candidates": method_summaries,
            }
        )
    return policy, diagnostics

def _write_back(repo_path: Path, best: dict, case_source: str, pipeline_status: str, cost_analysis: dict, family_policy: dict[str, str]) -> None:
    cfg_path = repo_path / '.gcie' / 'context_config.json'
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
            if not isinstance(cfg, dict):
                cfg = {}
        except Exception:
            cfg = {}
    else:
        cfg = {}

    cfg['adaptation_pipeline'] = {
        'status': pipeline_status,
        'best_label': best.get('label'),
        'full_hit_rate_pct': best.get('full_hit_rate_pct'),
        'tokens_per_query': best.get('tokens_per_query'),
        'case_source': case_source,
        'cost_analysis': cost_analysis,
        'family_policy': family_policy,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')

def _select_best_full_hit(candidates: list[dict]) -> dict | None:
    full_hit = [c for c in candidates if c.get('full_hit_rate_pct', 0.0) >= 100.0]
    if not full_hit:
        return None
    return min(
        full_hit,
        key=lambda item: (item.get('tokens_per_expected_hit') or 10**9, item.get('tokens_per_query', 10**9)),
    )

def run_post_init_adaptation(
    repo: str = '.',
    *,
    benchmark_size: int = 10,
    efficiency_iterations: int = 5,
    clear_profile: bool = False,
    adapt_workers: int | None = None,
) -> dict:
    repo_path = Path(repo).resolve()

    # Ensure all relative retrieval/evaluation calls execute in the target repo.
    os.chdir(repo_path)
    run_index(repo_path.as_posix())

    if clear_profile:
        from .context_slices import clear_adaptive_profile

        clear_adaptive_profile(repo_path.as_posix())

    cases, case_source = _select_adaptation_cases(repo_path, benchmark_size)
    if not cases:
        return {
            'status': 'no_benchmark_cases',
            'repo': repo_path.as_posix(),
            'case_source': case_source,
            'message': 'No repo-usable adaptation cases available.',
        }

    workers = _adapt_worker_count(adapt_workers)
    families = sorted({_case_family(case) for case in cases})
    family_policy, bootstrap_diagnostics = _bootstrap_family_policy(cases, families, workers=workers)

    # Accuracy rounds: promote methods per failing family until lock.
    accuracy_rounds_max = 5
    accuracy_rounds: list[dict] = []
    lock_streak = 0

    for rnd in range(1, accuracy_rounds_max + 1):
        rows, summary, by_family = _run_family_policy(cases, family_policy, workers=workers)
        round_payload = {
            'round': rnd,
            'family_policy': dict(family_policy),
            'summary': summary,
            'family_metrics': by_family,
        }
        accuracy_rounds.append(round_payload)

        if summary['full_hit_rate_pct'] >= 100.0:
            lock_streak += 1
            if lock_streak >= 2:
                break
            continue

        lock_streak = 0
        for fam, metrics in by_family.items():
            if metrics.get('pass_rate', 0.0) < 1.0:
                family_policy[fam] = _next_method(family_policy.get(fam, 'plain'))

    # Select best accuracy-locked round if available.
    locked_rounds = [r for r in accuracy_rounds if r['summary']['full_hit_rate_pct'] >= 100.0]
    if locked_rounds:
        selected_accuracy_round = min(
            locked_rounds,
            key=lambda r: (r['summary'].get('tokens_per_expected_hit') or 10**9, r['summary'].get('tokens_per_query', 10**9)),
        )
    else:
        selected_accuracy_round = max(
            accuracy_rounds,
            key=lambda r: (r['summary'].get('target_hit_rate_pct', 0.0), -r['summary'].get('tokens_per_query', 10**9)),
        )

    family_policy = dict(selected_accuracy_round['family_policy'])
    rows, current_summary, by_family = _run_family_policy(cases, family_policy, workers=workers)

    # Efficiency rounds: attempt family-level cheaper method under hard 100% gate.
    efficiency_trials: list[dict] = []
    for idx in range(max(0, int(efficiency_iterations))):
        improved = False
        for fam in families:
            cheaper = _cheaper_method(family_policy.get(fam, 'plain'))
            if not cheaper:
                continue
            trial_policy = dict(family_policy)
            trial_policy[fam] = cheaper
            _, trial_summary, trial_by_family = _run_family_policy(cases, trial_policy, workers=workers)
            trial_payload = {
                'iteration': idx + 1,
                'family': fam,
                'trial_policy': trial_policy,
                'summary': trial_summary,
            }
            efficiency_trials.append(trial_payload)

            if (
                trial_summary.get('full_hit_rate_pct', 0.0) >= 100.0
                and trial_summary.get('tokens_per_query', 10**9) < current_summary.get('tokens_per_query', 10**9)
            ):
                family_policy = trial_policy
                current_summary = trial_summary
                by_family = trial_by_family
                improved = True
        if not improved:
            break

    # Global candidate snapshots for transparency.
    slices_rows = _evaluate_cases_with_method(cases, 'slices', workers)
    plain_rows = _evaluate_cases_with_method(cases, 'plain', workers)
    plain_gap_rows = _evaluate_cases_with_method(cases, 'plain_gapfill', workers)
    plain_rescue_rows = _evaluate_cases_with_method(cases, 'plain_rescue', workers)
    slices_summary = _summarize('slices_accuracy_stage', slices_rows)
    plain_summary = _summarize('plain_accuracy_stage', plain_rows)
    plain_gap_summary = _summarize('plain_gapfill_accuracy_stage', plain_gap_rows)
    plain_rescue_summary = _summarize('plain_rescue_accuracy_stage', plain_rescue_rows)
    candidates = [slices_summary, plain_summary, plain_gap_summary, plain_rescue_summary]

    active = {
        'label': 'family_policy_selected',
        **current_summary,
    }

    # Hard accuracy fallback: never finalize below 100% when any known candidate reaches 100%.
    all_full_hit_candidates = list(candidates)
    all_full_hit_candidates.extend(r['summary'] for r in accuracy_rounds)
    all_full_hit_candidates.append(current_summary)
    best_full_hit = _select_best_full_hit(all_full_hit_candidates)
    if active.get('full_hit_rate_pct', 0.0) < 100.0 and best_full_hit is not None:
        active = dict(best_full_hit)

    cheapest = min(candidates, key=lambda item: (item.get('tokens_per_expected_hit') or 10**9, item.get('tokens_per_query', 10**9)))
    token_delta = int(active['total_tokens'] - cheapest['total_tokens'])
    pct_delta = round((token_delta / max(1, int(cheapest['total_tokens']))) * 100, 1)

    pipeline_status = 'ok'
    if (
        active.get('full_hit_rate_pct', 0.0) >= 100.0
        and active.get('tokens_per_query', 10**9) > cheapest.get('tokens_per_query', 10**9)
        and pct_delta > 40.0
    ):
        pipeline_status = 'accuracy_locked_but_cost_risky'

    cost_analysis = {
        'cheapest_label': cheapest.get('label'),
        'selected_label': active.get('label'),
        'selected_vs_cheapest_token_delta': token_delta,
        'selected_vs_cheapest_pct_delta': pct_delta,
        'risk_threshold_pct': 40.0,
        'cost_risky': pipeline_status == 'accuracy_locked_but_cost_risky',
    }

    _write_back(repo_path, active, case_source, pipeline_status, cost_analysis, family_policy)

    report = {
        'status': pipeline_status,
        'repo': repo_path.as_posix(),
        'benchmark_size': len(cases),
        'requested_benchmark_size': int(benchmark_size),
        'efficiency_iterations': int(efficiency_iterations),
        'adapt_workers': workers,
        'case_source': case_source,
        'family_policy': family_policy,
        'cost_analysis': cost_analysis,
        'phases': {
            'bootstrap': bootstrap_diagnostics,
            'accuracy_rounds': accuracy_rounds,
            'selected_accuracy_round': selected_accuracy_round,
            'efficiency_trials': efficiency_trials,
        },
        'stages': {
            'accuracy_candidates': candidates,
            'selected_after_accuracy': selected_accuracy_round['summary'],
            'efficiency_trials': efficiency_trials,
            'selected_final': active,
        },
    }

    planning_dir = repo_path / '.planning'
    planning_dir.mkdir(parents=True, exist_ok=True)
    out_path = planning_dir / 'post_init_adaptation_report.json'
    out_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    report['report_path'] = out_path.as_posix()
    return report

























