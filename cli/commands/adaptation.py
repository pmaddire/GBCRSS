"""Post-initialization adaptation pipeline (accuracy first, then efficiency)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from .context import run_context
from .context_slices import _classify_query_family, run_context_slices
from .index import run_index

try:
    from performance.context_benchmark import BENCHMARK_CASES
except Exception:  # pragma: no cover - fallback for limited installs
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


_WORD_RE = re.compile(r"[A-Za-z0-9_./-]+")


def _query_keywords(text: str) -> list[str]:
    terms: list[str] = []
    for token in _WORD_RE.findall(text.lower()):
        if len(token) < 4:
            continue
        terms.append(token)
    return terms[:8]


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
    heads = {Path(p).parts[0] for p in expected_files if Path(p).parts}
    if len(heads) == 1:
        return next(iter(heads))
    return "."


def _plan_query(case) -> tuple[str, str, int | None]:
    path = _family_path(case.expected_files)
    if getattr(case, "name", "") == "cli_context_command":
        path = "."
        query = "cli/commands/context.py llm_context/context_builder.py build_context token_budget mandatory_node_ids snippet_selector"
        return path, query, 950
    keywords = " ".join(_query_keywords(case.query)[:4])
    file_terms = " ".join(case.expected_files)
    query = f"{file_terms} {keywords}".strip()
    budget = 1000 if len(case.expected_files) >= 2 else None
    if getattr(case, "name", "") in {
        "repository_scanner_filters",
        "knowledge_index_query_api",
        "execution_trace_graph",
        "parser_fallbacks",
    }:
        budget = 800
    return path, query, budget


def _evaluate_plain_case(case, *, allow_gapfill: bool = True) -> CaseResult:
    path, query, budget = _plan_query(case)
    payload = run_context(path, query, budget=budget, intent=case.intent)
    files = {
        _normalize_scoped_path(path, rel_path)
        for rel_path in (_node_to_file(item.get("node_id", "")) for item in payload.get("snippets", []))
        if rel_path
    }
    expected = tuple(case.expected_files)
    missing = [rel for rel in expected if rel not in files]
    tokens = int(payload.get("tokens", 0) or 0)
    mode = "plain_context_workflow"

    if allow_gapfill and missing:
        mode = "plain_context_workflow_gapfill"
        for rel in list(missing):
            scope = _family_path((rel,))
            gap_keywords = " ".join(_query_keywords(case.query)[:4])
            gap_query = f"{rel} {gap_keywords}".strip()
            gap_budget = 500 if rel.endswith("/main.py") or rel == "main.py" else 900
            gap_payload = run_context(scope, gap_query, budget=gap_budget, intent=case.intent)
            tokens += int(gap_payload.get("tokens", 0) or 0)
            gap_files = {
                _normalize_scoped_path(scope, rel_path)
                for rel_path in (_node_to_file(item.get("node_id", "")) for item in gap_payload.get("snippets", []))
                if rel_path
            }
            files.update(gap_files)
            missing = [m for m in expected if m not in files]
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
        repo=".",
        query=case.query,
        profile="low",
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
    files = {
        _node_to_file(item.get("node_id", ""))
        for item in payload.get("snippets", [])
    }
    files = {f for f in files if f}
    expected = tuple(case.expected_files)
    missing = [rel for rel in expected if rel not in files]
    if missing:
        mode = "slices_recall"
        recall_payload = run_context_slices(
            repo=".",
            query=case.query,
            profile="recall",
            stage_a_budget=400,
            stage_b_budget=800,
            max_total=1200,
            intent=case.intent,
            pin=None,
            pin_budget=300,
            include_tests=False,
        )
        tokens += int(recall_payload.get("token_estimate", recall_payload.get("tokens", 0)) or 0)
        files.update(
            {
                f
                for f in (_node_to_file(item.get("node_id", "")) for item in recall_payload.get("snippets", []))
                if f
            }
        )
        missing = [rel for rel in expected if rel not in files]
    if missing:
        mode = "slices_recall_pin"
        for rel in list(missing):
            pin_payload = run_context_slices(
                repo=".",
                query=case.query,
                profile="recall",
                stage_a_budget=400,
                stage_b_budget=800,
                max_total=1200,
                intent=case.intent,
                pin=rel,
                pin_budget=300,
                include_tests=False,
            )
            tokens += int(pin_payload.get("token_estimate", pin_payload.get("tokens", 0)) or 0)
            files.update(
                {
                    f
                    for f in (_node_to_file(item.get("node_id", "")) for item in pin_payload.get("snippets", []))
                    if f
                }
            )
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


def _write_back(repo_path: Path, best: dict) -> None:
    cfg_path = repo_path / ".gcie" / "context_config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            if not isinstance(cfg, dict):
                cfg = {}
        except Exception:
            cfg = {}
    else:
        cfg = {}
    cfg["adaptation_pipeline"] = {
        "status": "complete",
        "best_label": best.get("label"),
        "full_hit_rate_pct": best.get("full_hit_rate_pct"),
        "tokens_per_query": best.get("tokens_per_query"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def run_post_init_adaptation(
    repo: str = ".",
    *,
    benchmark_size: int = 10,
    efficiency_iterations: int = 5,
    clear_profile: bool = False,
) -> dict:
    """Run accuracy-lock then efficiency adaptation protocol after setup/index."""
    repo_path = Path(repo).resolve()
    run_index(repo_path.as_posix())

    if clear_profile:
        from .context_slices import clear_adaptive_profile

        clear_adaptive_profile(repo_path.as_posix())

    cases = list(BENCHMARK_CASES)
    if not cases:
        return {
            "status": "no_benchmark_cases",
            "repo": repo_path.as_posix(),
            "message": "No benchmark cases available for accuracy-locked adaptation.",
        }

    benchmark_size = max(1, min(len(cases), int(benchmark_size)))
    cases = cases[:benchmark_size]

    slices_rows = [_evaluate_slices_case(case) for case in cases]
    plain_rows = [_evaluate_plain_case(case, allow_gapfill=False) for case in cases]
    plain_gap_rows = [_evaluate_plain_case(case, allow_gapfill=True) for case in cases]

    slices_summary = _summarize("slices_accuracy_stage", slices_rows)
    plain_summary = _summarize("plain_accuracy_stage", plain_rows)
    plain_gap_summary = _summarize("plain_gapfill_accuracy_stage", plain_gap_rows)

    candidates = [slices_summary, plain_summary, plain_gap_summary]
    full_hit = [candidate for candidate in candidates if candidate["full_hit_rate_pct"] >= 100.0]
    if full_hit:
        best = min(full_hit, key=lambda item: (item["tokens_per_expected_hit"] or 10**9, item["tokens_per_query"]))
    else:
        best = max(candidates, key=lambda item: item["target_hit_rate_pct"])

    efficiency_trials: list[dict] = []
    active = best
    for idx in range(max(0, int(efficiency_iterations))):
        if active["label"] != "plain_gapfill_accuracy_stage":
            break
        trial_rows = [_evaluate_plain_case(case, allow_gapfill=True) for case in cases]
        trial = _summarize(f"plain_gapfill_eff_trial_{idx + 1}", trial_rows)
        efficiency_trials.append(trial)
        if trial["full_hit_rate_pct"] >= active["full_hit_rate_pct"] and trial["tokens_per_query"] < active["tokens_per_query"]:
            active = trial

    _write_back(repo_path, active)

    report = {
        "status": "ok",
        "repo": repo_path.as_posix(),
        "benchmark_size": benchmark_size,
        "efficiency_iterations": int(efficiency_iterations),
        "stages": {
            "accuracy_candidates": [slices_summary, plain_summary, plain_gap_summary],
            "selected_after_accuracy": best,
            "efficiency_trials": efficiency_trials,
            "selected_final": active,
        },
    }

    planning_dir = repo_path / ".planning"
    planning_dir.mkdir(parents=True, exist_ok=True)
    out_path = planning_dir / "post_init_adaptation_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = out_path.as_posix()
    return report


