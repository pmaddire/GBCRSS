"""CLI command: context slices."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import re
import json

from llm_context.snippet_selector import estimate_tokens

from context.context_router import route_context

from .context import run_context


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

_BACKEND_KEYWORDS = {
    "backend",
    "api",
    "endpoint",
    "server",
    "service",
    "pipeline",
    "worker",
    "job",
    "queue",
    "model",
    "schema",
    "db",
    "database",
    "sql",
    "migration",
    "redis",
    "cache",
    "auth",
    "controller",
    "router",
}

_WIRING_KEYWORDS = {
    "wiring",
    "route",
    "routes",
    "router",
    "entry",
    "bootstrap",
    "app",
    "main",
    "index",
    "init",
}

_TEST_KEYWORDS = {
    "test",
    "tests",
    "spec",
    "pytest",
    "coverage",
    "regression",
}

_PROFILE_SETTINGS = {
    "recall": {
        "stage_a_budget": 400,
        "stage_b_budget": 800,
        "max_total": 1200,
        "pin_budget": 300,
        "include_tests": False,
    },
    "low": {
        "stage_a_budget": 300,
        "stage_b_budget": 600,
        "max_total": 800,
        "pin_budget": 200,
        "include_tests": False,
    },
    "adaptive": {
        "stage_a_budget": 350,
        "stage_b_budget": 700,
        "max_total": 1000,
        "pin_budget": 250,
        "include_tests": False,
    },
}

_ADAPTIVE_PROFILE_FILE = ".gcie/retrieval_profile.json"
_FAMILY_BUDGET_BOUNDS = {
    "single_file": {"stage_a_min": 250, "stage_a_max": 500, "stage_b_min": 500, "stage_b_max": 900, "max_total_min": 800, "max_total_max": 1400},
    "same_layer_pair": {"stage_a_min": 275, "stage_a_max": 600, "stage_b_min": 600, "stage_b_max": 1000, "max_total_min": 900, "max_total_max": 1600},
    "cross_layer": {"stage_a_min": 325, "stage_a_max": 700, "stage_b_min": 700, "stage_b_max": 1200, "max_total_min": 1050, "max_total_max": 2000},
    "backend_chain": {"stage_a_min": 350, "stage_a_max": 750, "stage_b_min": 800, "stage_b_max": 1300, "max_total_min": 1200, "max_total_max": 2200},
    "multi_hop": {"stage_a_min": 375, "stage_a_max": 800, "stage_b_min": 850, "stage_b_max": 1400, "max_total_min": 1300, "max_total_max": 2400},
    "architecture": {"stage_a_min": 325, "stage_a_max": 750, "stage_b_min": 800, "stage_b_max": 1400, "max_total_min": 1150, "max_total_max": 2300},
    "default": {"stage_a_min": 275, "stage_a_max": 650, "stage_b_min": 650, "stage_b_max": 1100, "max_total_min": 900, "max_total_max": 1800},
}

_DEFAULT_FAMILY_BUDGETS = {
    "single_file": {"stage_a": 300, "stage_b": 600, "max_total": 900},
    "same_layer_pair": {"stage_a": 350, "stage_b": 700, "max_total": 1100},
    "cross_layer": {"stage_a": 400, "stage_b": 850, "max_total": 1300},
    "backend_chain": {"stage_a": 425, "stage_b": 900, "max_total": 1400},
    "multi_hop": {"stage_a": 450, "stage_b": 950, "max_total": 1500},
    "architecture": {"stage_a": 400, "stage_b": 850, "max_total": 1300},
    "default": {"stage_a": 350, "stage_b": 700, "max_total": 1100},
}
_FAMILY_KEYWORDS = {
    "architecture": {"architecture", "fallback", "router", "routing", "confidence", "bootstrap", "index", "slicer"},
    "multi_hop": {"stage", "pipeline", "workflow", "orchestrator", "chain"},
    "backend_chain": {"backend", "api_key", "config", "llm", "openai", "service", "worker"},
}

_NON_LEARNABLE_SEGMENTS = {"docs", "get-shit-done", ".planning", ".gcie", "node_modules", "__pycache__"}
_SOURCE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cs", ".cpp", ".c", ".h"}
_ROLE_HINTS = {
    "fallback": ("fallback", "router", "evaluator", "route"),
    "routing": ("router", "route", "routing"),
    "router": ("router", "route", "routing"),
    "bootstrap": ("bootstrap", "init", "index", "architecture"),
    "bootstrapped": ("bootstrap", "init", "index", "architecture"),
    "managed": ("index", "architecture", "bootstrap"),
    "architecture": ("architecture", "router", "fallback", "index", "bootstrap"),
    "index": ("index", "architecture"),
}

_STRICT_ROLE_PATH_TOKENS = {
    "fallback": ("fallback", "evaluator"),
    "routing": ("router", "route"),
    "router": ("router", "route"),
    "bootstrap": ("bootstrap",),
    "bootstrapped": ("bootstrap",),
    "managed": ("managed", "index"),
}

def _slice_path(repo: str, segment: str) -> str:
    return str(Path(repo) / segment)


def _frontend_bias(query: str) -> bool:
    text = query.lower()
    return any(keyword in text for keyword in _FRONTEND_KEYWORDS)


def _backend_bias(query: str) -> bool:
    text = query.lower()
    return any(keyword in text for keyword in _BACKEND_KEYWORDS)


def _wiring_needed(query: str) -> bool:
    text = query.lower()
    return any(keyword in text for keyword in _WIRING_KEYWORDS)


def _needs_tests(query: str, include_tests: bool) -> bool:
    if include_tests:
        return True
    text = query.lower()
    return any(keyword in text for keyword in _TEST_KEYWORDS)


def _query_tokens(query: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-Z0-9_./-]+", query.lower()) if token]


def _explicit_file_tokens(query: str) -> list[str]:
    exts = (".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json", ".yaml", ".yml")
    return [token for token in _query_tokens(query) if token.endswith(exts)]


def _top_segment(path_token: str) -> str | None:
    normalized = path_token.replace("\\", "/").strip("/")
    if not normalized:
        return None
    if "/" not in normalized:
        return None
    return normalized.split("/", 1)[0]


def _classify_query_family(query: str) -> str:
    tokens = _query_tokens(query)
    token_set = set(tokens)
    explicit = _explicit_file_tokens(query)

    has_frontend = any(token.startswith("frontend/") for token in explicit) or any("frontend" in token for token in token_set)
    has_backend = any(token.endswith(".py") for token in explicit) or any(token in _BACKEND_KEYWORDS for token in token_set)

    if any(token in _FAMILY_KEYWORDS["architecture"] for token in token_set):
        return "architecture"
    if len(explicit) >= 3 or any(token in _FAMILY_KEYWORDS["multi_hop"] for token in token_set):
        return "multi_hop"
    if has_frontend and has_backend:
        return "cross_layer"
    if any(token in _FAMILY_KEYWORDS["backend_chain"] for token in token_set):
        return "backend_chain"
    if len(explicit) >= 2:
        return "same_layer_pair"
    if len(explicit) == 1:
        return "single_file"
    return "default"


def _adaptive_profile_path(repo_path: Path) -> Path:
    return repo_path / _ADAPTIVE_PROFILE_FILE


def _load_adaptive_profile(repo_path: Path) -> dict:
    path = _adaptive_profile_path(repo_path)
    if not path.exists():
        return {"version": 1, "updated_at": None, "families": {}, "slice_stats": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "updated_at": None, "families": {}, "slice_stats": {}}
    if not isinstance(data, dict):
        return {"version": 1, "updated_at": None, "families": {}, "slice_stats": {}}
    data.setdefault("version", 1)
    data.setdefault("updated_at", None)
    data.setdefault("families", {})
    data.setdefault("slice_stats", {})
    return data


def _save_adaptive_profile(repo_path: Path, data: dict) -> None:
    path = _adaptive_profile_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")



def adaptive_profile_summary(repo: str) -> dict:
    """Return a compact summary of learned adaptive retrieval behavior."""
    repo_path = Path(repo)
    profile = _load_adaptive_profile(repo_path)
    families = profile.get("families", {})
    rows: list[dict] = []
    for family_name, entry in sorted(families.items(), key=lambda item: str(item[0])):
        if not isinstance(entry, dict):
            continue
        runs = int(entry.get("runs", 0))
        hits = int(entry.get("hits", 0))
        tokens_total = int(entry.get("tokens_total", 0))
        rows.append(
            {
                "family": family_name,
                "runs": runs,
                "hit_rate": round((hits / runs), 3) if runs else 0.0,
                "avg_tokens": round((tokens_total / runs), 1) if runs else 0.0,
                "stage_a": int(entry.get("stage_a", 0)),
                "stage_b": int(entry.get("stage_b", 0)),
                "max_total": int(entry.get("max_total", 0)),
                "preferred_slices": entry.get("preferred_slices", []),
            }
        )

    return {
        "profile_path": _adaptive_profile_path(repo_path).as_posix(),
        "updated_at": profile.get("updated_at"),
        "families": rows,
        "slice_stats": profile.get("slice_stats", {}),
    }


def clear_adaptive_profile(repo: str) -> dict:
    """Reset adaptive learning state for a repo."""
    repo_path = Path(repo)
    path = _adaptive_profile_path(repo_path)
    profile = {"version": 1, "updated_at": None, "families": {}, "slice_stats": {}}
    _save_adaptive_profile(repo_path, profile)
    return {
        "profile_path": path.as_posix(),
        "cleared": True,
        "families": 0,
    }
def _family_bounds(family: str) -> dict:
    return _FAMILY_BUDGET_BOUNDS.get(family, _FAMILY_BUDGET_BOUNDS["default"])


def _clamp_family_budgets(family: str, stage_a: int, stage_b: int, max_total: int) -> tuple[int, int, int]:
    bounds = _family_bounds(family)
    clamped_a = min(bounds["stage_a_max"], max(bounds["stage_a_min"], int(stage_a)))
    clamped_b = min(bounds["stage_b_max"], max(bounds["stage_b_min"], int(stage_b)))
    clamped_total = min(bounds["max_total_max"], max(bounds["max_total_min"], int(max_total)))
    return clamped_a, clamped_b, clamped_total



def _expanded_slice_budget(max_total: int, *, missing_count: int, required_count: int) -> int:
    if missing_count <= 0:
        return int(max_total)
    additive = max(200, int(max_total * 0.35))
    if required_count >= 3 or missing_count >= 2:
        additive = max(additive, int(max_total * 0.5))
    cap = max_total + min(900, additive)
    return max(max_total, cap)


def _direct_fallback_budget(max_total: int) -> tuple[int, int]:
    # Keep direct fallback bounded to avoid token blow-ups.
    retrieval_budget = max_total + min(500, max(250, int(max_total * 0.4)))
    merge_cap = max_total + min(700, max(300, int(max_total * 0.6)))
    return retrieval_budget, merge_cap
def _missing_target_segments(missing_targets: list[str]) -> list[str]:
    segments: list[str] = []
    for target in missing_targets:
        segment = _top_segment(target)
        if not segment:
            continue
        s = segment.lower()
        if s in _NON_LEARNABLE_SEGMENTS:
            continue
        if s not in segments:
            segments.append(s)
    return segments[:3]


def _family_defaults(family: str) -> dict:
    base = _DEFAULT_FAMILY_BUDGETS.get(family, _DEFAULT_FAMILY_BUDGETS["default"])
    return {"stage_a": int(base["stage_a"]), "stage_b": int(base["stage_b"]), "max_total": int(base["max_total"]), "preferred_slices": []}


def _resolve_adaptive_settings(repo_path: Path, family: str) -> dict:
    defaults = _family_defaults(family)
    profile = _load_adaptive_profile(repo_path)
    learned = profile.get("families", {}).get(family)
    if not isinstance(learned, dict):
        return defaults

    runs = int(learned.get("runs", 0))
    hits = int(learned.get("hits", 0))
    hit_rate = (hits / runs) if runs else 0.0
    consecutive_misses = int(learned.get("consecutive_misses", 0))

    out = defaults.copy()
    if runs >= 3 and hit_rate >= 0.67:
        out["stage_a"] = int(learned.get("stage_a", out["stage_a"]))
        out["stage_b"] = int(learned.get("stage_b", out["stage_b"]))
        out["max_total"] = int(learned.get("max_total", out["max_total"]))

    # Scope-first correction: on repeated misses, trust learned slices before widening budgets.
    slices = learned.get("preferred_slices", [])
    if isinstance(slices, list):
        out["preferred_slices"] = [str(item) for item in slices if str(item) not in _NON_LEARNABLE_SEGMENTS][:3]

    # If miss streak is active, hold stage_a and use stable safety floor for retries.
    if consecutive_misses >= 2:
        out["stage_a"] = max(defaults["stage_a"], out["stage_a"])
        out["stage_b"] = max(defaults["stage_b"], out["stage_b"])

    out["stage_a"], out["stage_b"], out["max_total"] = _clamp_family_budgets(
        family,
        out["stage_a"],
        out["stage_b"],
        out["max_total"],
    )
    return out


def _available_slice_dirs(repo_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for child in repo_path.iterdir():
            if child.is_dir() and child.name not in {".git", ".gcie", ".venv", "node_modules", "__pycache__"}:
                out[child.name.lower()] = child.as_posix()
    except Exception:
        return out
    return out


def _select_slices(
    repo: str,
    query: str,
    *,
    include_tests: bool,
    preferred_slices: list[str] | None = None,
) -> list[tuple[str, str]]:
    repo_path = Path(repo)
    available = _available_slice_dirs(repo_path)

    selected: list[str] = []

    for item in preferred_slices or []:
        key = item.lower()
        if key in available and key not in selected:
            selected.append(key)

    for token in _explicit_file_tokens(query):
        segment = _top_segment(token)
        if segment and segment.lower() in available and segment.lower() not in selected:
            selected.append(segment.lower())

    frontend_bias = _frontend_bias(query)
    backend_bias = _backend_bias(query)

    if frontend_bias and "frontend" in available and "frontend" not in selected:
        selected.append("frontend")
    if (backend_bias or not frontend_bias) and "backend" in available and "backend" not in selected:
        selected.append("backend")

    if not selected:
        if "frontend" in available:
            selected.append("frontend")
        if "backend" in available:
            selected.append("backend")

    if _needs_tests(query, include_tests) and "tests" in available and "tests" not in selected:
        selected.append("tests")

    # Keep slice fan-out tight for token discipline.
    selected = selected[:4]

    return [(name, available[name]) for name in selected if name in available]


def _architecture_preferred_slices(repo_path: Path) -> list[str]:
    candidates: list[str] = []
    for name in _available_slice_dirs(repo_path).keys():
        lowered = name.lower()
        if any(token in lowered for token in ("context", "architect", "routing", "router", "core", "retrieval")):
            candidates.append(name)
    # keep stable order and tight fan-out
    return sorted(set(candidates))[:3]


def _is_better_payload(candidate: dict, candidate_signal: dict, current: dict, current_signal: dict) -> bool:
    cand_tuple = (
        1 if candidate_signal.get("hit") else 0,
        int(candidate_signal.get("target_hits", 0)),
        -len(candidate_signal.get("missing_targets", [])),
        -int(candidate.get("token_estimate", 0) or 0),
    )
    curr_tuple = (
        1 if current_signal.get("hit") else 0,
        int(current_signal.get("target_hits", 0)),
        -len(current_signal.get("missing_targets", [])),
        -int(current.get("token_estimate", 0) or 0),
    )
    return cand_tuple > curr_tuple


def _node_file_path(node_id: str) -> str:
    if node_id.startswith("file:"):
        return node_id[len("file:") :]
    if node_id.startswith("function:"):
        return node_id[len("function:") :].split("::", 1)[0]
    if node_id.startswith("class:"):
        return node_id[len("class:") :].split("::", 1)[0]
    return ""


def _infer_slice_from_path(path: str) -> str:
    lowered = path.replace("\\", "/").lower()
    if "/frontend/" in lowered or lowered.startswith("frontend/"):
        return "frontend"
    if "/backend/" in lowered or lowered.startswith("backend/"):
        return "backend"
    if "/tests/" in lowered or lowered.startswith("tests/"):
        return "tests"
    return "pin"


def _is_test_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    if "/tests/" in lowered or lowered.startswith("tests/"):
        return True
    filename = Path(lowered).name
    return (
        filename.startswith("test_")
        or filename.endswith("_test.py")
        or ".test." in filename
        or ".spec." in filename
    )


def _is_wiring_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    filename = Path(lowered).name
    wiring_names = {
        "app.py",
        "main.py",
        "server.py",
        "wsgi.py",
        "asgi.py",
        "app.js",
        "app.jsx",
        "app.ts",
        "app.tsx",
        "main.js",
        "main.jsx",
        "main.ts",
        "main.tsx",
        "index.js",
        "index.jsx",
        "index.ts",
        "index.tsx",
    }
    if filename in wiring_names:
        return True
    return any(token in lowered for token in ("/routes/", "/router/"))


def _classify_roles(path: str) -> set[str]:
    roles: set[str] = set()
    if _is_test_path(path):
        roles.add("test")
        return roles
    if _is_wiring_path(path):
        roles.add("wiring")
    roles.add("implementation")
    return roles


def _dedupe_by_file(snippets: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for item in snippets:
        path = _node_file_path(item.get("node_id", ""))
        if not path:
            continue
        current = best.get(path)
        if current is None or item.get("score", 0.0) > current.get("score", 0.0):
            best[path] = item
    return sorted(best.values(), key=lambda s: s.get("score", 0.0), reverse=True)


_EXCLUDE_GLOBS = ["!**/.gcie/**", "!**/.git/**", "!**/.venv/**", "!**/node_modules/**"]
_INCLUDE_GLOBS = ["**/*.py", "**/*.md", "**/*.js", "**/*.ts", "**/*.tsx"]


def _rg_top_files(query: str, top_n: int = 5) -> list[str]:
    terms = [t for t in re.split(r"[^A-Za-z0-9_]+", query.lower()) if len(t) >= 3]
    if not terms:
        return []
    pattern = "|".join(re.escape(t) for t in sorted(set(terms)))
    cmd = ["rg", "--count", "-i", pattern]
    for g in _INCLUDE_GLOBS:
        cmd.extend(["-g", g])
    for g in _EXCLUDE_GLOBS:
        cmd.extend(["-g", g])
    cmd.append(".")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except Exception:
        return []
    counts = {}
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        path, count = line.rsplit(":", 1)
        try:
            counts[path] = int(count.strip())
        except ValueError:
            continue
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [path for path, _ in ranked[:top_n]]



def _index_files_for_query(query: str) -> list[str]:
    index_path = Path(".gcie") / "architecture_index.json"
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    tokens = [t for t in re.split(r"[^A-Za-z0-9_]+", query.lower()) if len(t) >= 3]
    if not tokens:
        return []
    files: list[str] = []
    for subsystem in data.get("subsystems", []):
        name = (subsystem.get("name") or "").lower()
        if not name:
            continue
        key_files = subsystem.get("key_files", []) or []
        if any(token in name or name in token for token in tokens):
            for path in key_files:
                files.append(path)
            continue
        if any(token in (path.lower()) for path in key_files for token in tokens):
            for path in key_files:
                files.append(path)

    file_map = data.get("file_map", {})
    for path in file_map.keys():
        lowered = path.lower()
        if any(token in lowered for token in tokens):
            files.append(path)

    return files


def _file_snippet(path: Path, max_lines: int = 120) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    return "\n".join(lines[:max_lines]).strip()


def _index_guided_rescue_snippets(repo_path: Path, query: str, *, limit: int = 6) -> list[dict]:
    snippets: list[dict] = []
    seen: set[str] = set()
    for rel in _index_files_for_query(query):
        rel_norm = rel.replace("\\", "/")
        if rel_norm in seen:
            continue
        file_path = (repo_path / rel_norm).resolve() if not Path(rel_norm).is_absolute() else Path(rel_norm)
        if not file_path.exists() or not file_path.is_file():
            continue
        if not _is_source_like_path(file_path.as_posix()):
            continue
        content = _file_snippet(file_path)
        if not content:
            continue
        seen.add(rel_norm)
        snippets.append({
            "node_id": f"file:{rel_norm}",
            "score": 0.85,
            "content": content,
            "slice": _top_segment(rel_norm) or "pin",
        })
        if len(snippets) >= limit:
            break
    return snippets


def _merge_snippets(existing: list[dict], extra: list[dict], max_total: int) -> list[dict]:
    by_id: dict[str, dict] = {item.get("node_id", ""): item for item in existing}
    for item in extra:
        node_id = item.get("node_id", "")
        if node_id and node_id not in by_id:
            by_id[node_id] = item
    merged = list(by_id.values())
    merged.sort(key=lambda s: s.get("score", 0.0), reverse=True)
    out: list[dict] = []
    used = 0
    for item in merged:
        tokens = estimate_tokens(item.get("content", ""))
        if used + tokens > max_total:
            continue
        out.append(item)
        used += tokens
    return out


def _total_tokens(snippets: list[dict]) -> int:
    return sum(estimate_tokens(item.get("content", "")) for item in snippets)


def _found_roles_by_slice(snippets: list[dict]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for item in snippets:
        path = _node_file_path(item.get("node_id", ""))
        if not path:
            continue
        slice_name = item.get("slice", "unknown")
        roles = _classify_roles(path)
        found.setdefault(slice_name, set()).update(roles)
    return found


def _required_roles_for_slice(
    slice_name: str,
    query: str,
    *,
    include_tests: bool,
    pin: str | None,
    slice_names: set[str],
) -> set[str]:
    roles: set[str] = set()
    wiring_required = _frontend_bias(query) or _wiring_needed(query) or bool(pin)
    tests_required = _needs_tests(query, include_tests)

    if slice_name == "tests":
        if tests_required:
            roles.add("test")
        return roles

    roles.add("implementation")
    if wiring_required:
        if slice_name == "frontend" and "frontend" in slice_names:
            roles.add("wiring")
        elif slice_name == "backend" and "frontend" not in slice_names:
            roles.add("wiring")
    return roles


def _missing_required_slices(
    snippets: list[dict],
    slices: list[tuple[str, str]],
    query: str,
    *,
    include_tests: bool,
    pin: str | None,
) -> set[str]:
    slice_names = {name for name, _ in slices}
    found_roles = _found_roles_by_slice(snippets)
    missing: set[str] = set()
    for name, _ in slices:
        required_roles = _required_roles_for_slice(
            name,
            query,
            include_tests=include_tests,
            pin=pin,
            slice_names=slice_names,
        )
        if not required_roles:
            continue
        if not required_roles.issubset(found_roles.get(name, set())):
            missing.add(name)
    return missing


def _trim_to_budget(snippets: list[dict], max_total: int, required_slices: set[str]) -> list[dict]:
    # Ensure at least one snippet per required slice, if available.
    required: list[dict] = []
    remaining: list[dict] = []
    seen_required: set[str] = set()

    for item in snippets:
        slice_name = item.get("slice")
        if slice_name in required_slices and slice_name not in seen_required:
            required.append(item)
            seen_required.add(slice_name)
        else:
            remaining.append(item)

    ordered = required + remaining
    out: list[dict] = []
    used = 0
    for item in ordered:
        t = estimate_tokens(item.get("content", ""))
        if used + t > max_total and item.get("slice") not in required_slices:
            continue
        out.append(item)
        used += t
        if used >= max_total and all(s in seen_required for s in required_slices):
            break

    return out


def _apply_profile(
    profile: str | None,
    *,
    stage_a_budget: int,
    stage_b_budget: int,
    max_total: int,
    pin_budget: int,
    include_tests: bool,
) -> tuple[int, int, int, int, bool, str]:
    if not profile:
        return stage_a_budget, stage_b_budget, max_total, pin_budget, include_tests, "custom"

    key = profile.lower()
    settings = _PROFILE_SETTINGS.get(key)
    if settings is None:
        return stage_a_budget, stage_b_budget, max_total, pin_budget, include_tests, "custom"

    return (
        settings["stage_a_budget"],
        settings["stage_b_budget"],
        settings["max_total"],
        settings["pin_budget"],
        settings["include_tests"],
        key,
    )


def _record_slice_stats(bucket: dict, *, hit: bool, tokens: int) -> None:
    bucket["runs"] = int(bucket.get("runs", 0)) + 1
    bucket["hits"] = int(bucket.get("hits", 0)) + (1 if hit else 0)
    bucket["tokens_total"] = int(bucket.get("tokens_total", 0)) + int(tokens)


def _is_source_like_path(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in _SOURCE_EXTENSIONS


def _payload_files(payload: dict) -> list[str]:
    files: list[str] = []
    for item in payload.get("snippets", []):
        path = _node_file_path(item.get("node_id", ""))
        if path:
            files.append(path.replace("\\", "/"))
    return sorted(set(files))


def _target_matched(target: str, files: list[str]) -> bool:
    target_norm = target.replace("\\", "/").lower()
    target_name = Path(target_norm).name
    return any(
        file_path.lower() == target_norm
        or Path(file_path.lower()).name == target_name
        for file_path in files
    )


def _query_role_groups(query: str) -> list[tuple[str, ...]]:
    tokens = _query_tokens(query)
    groups: list[tuple[str, ...]] = []
    for token in tokens:
        role = _ROLE_HINTS.get(token)
        if role and role not in groups:
            groups.append(role)
    return groups[:3]


def _query_strict_roles(query: str) -> list[str]:
    tokens = _query_tokens(query)
    roles: list[str] = []
    for token in tokens:
        if token in _STRICT_ROLE_PATH_TOKENS and token not in roles:
            roles.append(token)
    return roles[:3]


def _adaptive_hit_signal(payload: dict, query: str) -> dict:
    files = _payload_files(payload)
    snippets = payload.get("snippets", [])
    explicit_targets = [
        token for token in _explicit_file_tokens(query) if ("/" in token or token.endswith(".py") or token.endswith(".jsx") or token.endswith(".ts") or token.endswith(".tsx"))
    ]

    target_hits = 0
    missing_targets: list[str] = []
    for target in explicit_targets:
        if _target_matched(target, files):
            target_hits += 1
        else:
            missing_targets.append(target)

    role_groups = _query_role_groups(query)
    role_hits = 0
    for group in role_groups:
        if any(any(role in path.lower() for role in group) for path in files):
            role_hits += 1

    strict_roles = _query_strict_roles(query)
    strict_role_hits = 0
    for role in strict_roles:
        tokens = _STRICT_ROLE_PATH_TOKENS.get(role, ())
        if any(any(token in path.lower() for token in tokens) for path in files):
            strict_role_hits += 1

    missing_after = payload.get("missing_required_slices_after")
    slices_ok = True
    if isinstance(missing_after, list):
        slices_ok = len(missing_after) == 0

    source_files = [path for path in files if _is_source_like_path(path)]
    has_sources = len(source_files) >= 1

    strict_ok = True
    if strict_roles:
        strict_ok = strict_role_hits >= max(1, len(strict_roles))

    if explicit_targets:
        hit = len(missing_targets) == 0 and bool(snippets) and has_sources and strict_ok
    else:
        if role_groups:
            hit = (role_hits >= max(1, min(len(role_groups), 2))) and bool(snippets) and has_sources and strict_ok
        else:
            hit = slices_ok and bool(snippets) and has_sources and strict_ok

    return {
        "hit": hit,
        "files": files,
        "missing_targets": missing_targets,
        "target_hits": target_hits,
        "target_total": len(explicit_targets),
        "role_hits": role_hits,
        "role_total": len(role_groups),
        "strict_role_hits": strict_role_hits,
        "strict_role_total": len(strict_roles),
        "has_sources": has_sources,
    }


def _update_adaptive_profile(
    repo_path: Path,
    *,
    family: str,
    query: str,
    payload: dict,
    stage_a_budget: int,
    stage_b_budget: int,
    max_total: int,
) -> None:
    profile = _load_adaptive_profile(repo_path)
    families = profile.setdefault("families", {})
    family_entry = families.get(family)
    if not isinstance(family_entry, dict):
        defaults = _family_defaults(family)
        family_entry = {
            "runs": 0,
            "hits": 0,
            "tokens_total": 0,
            "stage_a": defaults["stage_a"],
            "stage_b": defaults["stage_b"],
            "max_total": defaults["max_total"],
            "preferred_slices": [],
            "preferred_slice_counts": {},
            "consecutive_hits": 0,
            "consecutive_misses": 0,
        }

    tokens = int(payload.get("token_estimate", 0) or 0)
    signal = _adaptive_hit_signal(payload, query)
    hit = bool(signal["hit"])
    snippets = payload.get("snippets", [])

    _record_slice_stats(family_entry, hit=hit, tokens=tokens)

    slice_stats = profile.setdefault("slice_stats", {})
    selected_slices = payload.get("selected_slices", [])
    if not isinstance(selected_slices, list):
        selected_slices = []
    if not selected_slices:
        inferred: dict[str, int] = {}
        for file_path in signal["files"]:
            segment = _top_segment(file_path)
            if not segment:
                continue
            segment_l = segment.lower()
            if segment_l in _NON_LEARNABLE_SEGMENTS:
                continue
            if not _is_source_like_path(file_path):
                continue
            inferred[segment_l] = inferred.get(segment_l, 0) + 1
        selected_slices = [name for name, _ in sorted(inferred.items(), key=lambda item: (-item[1], item[0]))[:3]]

    for slice_name in selected_slices:
        key = str(slice_name)
        stats = slice_stats.get(key)
        if not isinstance(stats, dict):
            stats = {"runs": 0, "hits": 0, "tokens_total": 0}
        _record_slice_stats(stats, hit=hit, tokens=tokens)
        slice_stats[key] = stats

        pref_counts = family_entry.setdefault("preferred_slice_counts", {})
        pref_counts[key] = int(pref_counts.get(key, 0)) + (2 if hit else 1)

    runs = int(family_entry.get("runs", 0))
    hits = int(family_entry.get("hits", 0))
    hit_rate = (hits / runs) if runs else 0.0

    learned_a = int(family_entry.get("stage_a", stage_a_budget))
    learned_b = int(family_entry.get("stage_b", stage_b_budget))
    learned_total = int(family_entry.get("max_total", max_total))

    consecutive_hits = int(family_entry.get("consecutive_hits", 0))
    consecutive_misses = int(family_entry.get("consecutive_misses", 0))

    if hit:
        consecutive_hits += 1
        consecutive_misses = 0
        # Stability-gated step-down: only after 3 consecutive successful runs.
        if consecutive_hits >= 3 and hit_rate >= 0.90:
            learned_a -= 25
            learned_total -= 75
            consecutive_hits = 0
    else:
        consecutive_hits = 0
        consecutive_misses += 1

        # Scope-first correction: prefer slice learning before budget escalation.
        for segment in _missing_target_segments(signal["missing_targets"]):
            pref_counts = family_entry.setdefault("preferred_slice_counts", {})
            pref_counts[segment] = int(pref_counts.get(segment, 0)) + 4

        # Escalate retry budgets only on repeated misses.
        if consecutive_misses >= 2:
            learned_b += 100
            learned_total += 150

    learned_a, learned_b, learned_total = _clamp_family_budgets(family, learned_a, learned_b, learned_total)

    family_entry["stage_a"] = learned_a
    family_entry["stage_b"] = learned_b
    family_entry["max_total"] = learned_total
    family_entry["consecutive_hits"] = consecutive_hits
    family_entry["consecutive_misses"] = consecutive_misses

    pref_counts = family_entry.get("preferred_slice_counts", {})
    if isinstance(pref_counts, dict):
        ranked = sorted(pref_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
        family_entry["preferred_slices"] = [name for name, _ in ranked[:3]]

    family_entry["last_result"] = {
        "hit": hit,
        "tokens": tokens,
        "mode": payload.get("mode"),
        "missing_targets": signal["missing_targets"],
        "target_hits": signal["target_hits"],
        "target_total": signal["target_total"],
        "role_hits": signal["role_hits"],
        "role_total": signal["role_total"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    families[family] = family_entry
    profile["families"] = families
    profile["slice_stats"] = slice_stats
    _save_adaptive_profile(repo_path, profile)


def run_context_slices(
    repo: str,
    query: str,
    *,
    stage_a_budget: int,
    stage_b_budget: int,
    max_total: int,
    intent: str | None,
    pin: str | None,
    pin_budget: int,
    include_tests: bool,
    profile: str | None = None,
) -> dict:
    stage_a_budget, stage_b_budget, max_total, pin_budget, include_tests, profile_used = _apply_profile(
        profile,
        stage_a_budget=stage_a_budget,
        stage_b_budget=stage_b_budget,
        max_total=max_total,
        pin_budget=pin_budget,
        include_tests=include_tests,
    )

    repo_path = Path(repo)
    query_family = _classify_query_family(query)
    preferred_slices: list[str] | None = None

    if profile_used == "adaptive":
        adaptive = _resolve_adaptive_settings(repo_path, query_family)
        stage_a_budget = int(adaptive["stage_a"])
        stage_b_budget = int(adaptive["stage_b"])
        max_total = int(adaptive["max_total"])
        preferred_slices = list(adaptive.get("preferred_slices", []))

    payload = route_context(
        repo,
        query,
        intent=intent,
        max_total=max_total,
        profile=profile_used,
        normal_runner=lambda: run_context_slices_normal(
            repo,
            query,
            stage_a_budget=stage_a_budget,
            stage_b_budget=stage_b_budget,
            max_total=max_total,
            intent=intent,
            pin=pin,
            pin_budget=pin_budget,
            include_tests=include_tests,
            profile=profile_used,
            preferred_slices=preferred_slices,
        ),
    )

    if payload.get("mode") == "normal" and payload.get("fallback_reason"):
        fallback_budget, merge_cap = _direct_fallback_budget(max_total)
        direct = run_context(repo, query, budget=fallback_budget, intent=intent, top_k=60)
        snippets = direct.get("snippets", [])
        extra = []
        index_files = _index_files_for_query(query)
        if index_files:
            for rel in index_files:
                path = Path(rel)
                if not path.exists():
                    continue
                content = _file_snippet(path)
                if content:
                    extra.append({"node_id": f"file:{rel}", "score": 0.9, "content": content})
        else:
            for rel in _rg_top_files(query, top_n=12):
                path = Path(rel)
                if not path.exists():
                    continue
                content = _file_snippet(path)
                if content:
                    extra.append({"node_id": f"file:{rel}", "score": 0.2, "content": content})
        snippets = _merge_snippets(snippets, extra, max_total=merge_cap)

        payload = {
            "query": direct.get("query", query),
            "profile": profile_used,
            "mode": "direct",
            "intent": intent,
            "snippets": snippets,
            "token_estimate": _total_tokens(snippets),
            "fallback_reason": payload.get("fallback_reason"),
            "secondary_fallback": "normal_empty",
            "selected_slices": [],
            "missing_required_slices_after": [],
        }

    signal = _adaptive_hit_signal(payload, query)

    if profile_used == "adaptive" and query_family == "architecture" and not signal.get("hit"):
        arch_slices = _architecture_preferred_slices(repo_path)
        if arch_slices:
            rescue_query = f"{query} architecture fallback routing bootstrap index"
            rescue_payload = run_context_slices_normal(
                repo,
                rescue_query,
                stage_a_budget=stage_a_budget,
                stage_b_budget=stage_b_budget,
                max_total=max_total,
                intent=intent,
                pin=pin,
                pin_budget=pin_budget,
                include_tests=include_tests,
                profile=profile_used,
                preferred_slices=arch_slices,
            )
            rescue_signal = _adaptive_hit_signal(rescue_payload, query)
            rescue_payload["rescue_attempted"] = True
            rescue_payload["rescue_scopes"] = arch_slices
            if _is_better_payload(rescue_payload, rescue_signal, payload, signal):
                payload = rescue_payload
                signal = rescue_signal

    # General index-guided rescue for adaptive mode when coverage is still weak.
    if profile_used == "adaptive" and not signal.get("hit"):
        rescue_extra = _index_guided_rescue_snippets(repo_path, query, limit=6)
        if rescue_extra:
            merged_snippets = _merge_snippets(payload.get("snippets", []), rescue_extra, max_total=max_total * 2)
            candidate_payload = dict(payload)
            candidate_payload["snippets"] = merged_snippets
            candidate_payload["token_estimate"] = _total_tokens(merged_snippets)
            candidate_payload["index_rescue_used"] = True
            candidate_signal = _adaptive_hit_signal(candidate_payload, query)
            if _is_better_payload(candidate_payload, candidate_signal, payload, signal):
                payload = candidate_payload
                signal = candidate_signal

    payload["query_family"] = query_family
    payload["adaptive_profile"] = profile_used == "adaptive"
    payload["adaptive_signal"] = {
        "hit": bool(signal.get("hit")),
        "target_hits": int(signal.get("target_hits", 0)),
        "target_total": int(signal.get("target_total", 0)),
        "missing_targets": signal.get("missing_targets", []),
        "role_hits": int(signal.get("role_hits", 0)),
        "role_total": int(signal.get("role_total", 0)),
    }

    if profile_used == "adaptive":
        _update_adaptive_profile(
            repo_path,
            family=query_family,
            query=query,
            payload=payload,
            stage_a_budget=stage_a_budget,
            stage_b_budget=stage_b_budget,
            max_total=max_total,
        )

    return payload


def run_context_slices_normal(
    repo: str,
    query: str,
    *,
    stage_a_budget: int,
    stage_b_budget: int,
    max_total: int,
    intent: str | None,
    pin: str | None,
    pin_budget: int,
    include_tests: bool,
    profile: str | None,
    preferred_slices: list[str] | None = None,
) -> dict:
    repo_path = Path(repo)

    slices = _select_slices(
        repo,
        query,
        include_tests=include_tests,
        preferred_slices=preferred_slices,
    )

    results: dict[str, dict] = {}
    collected: list[dict] = []

    # Pin first (cheap, high signal)
    if pin:
        pin_path = str(repo_path / pin)
        if Path(pin_path).exists():
            pin_result = run_context(pin_path, query, budget=pin_budget, intent=intent)
            results["pin"] = pin_result
            for item in pin_result.get("snippets", []):
                node_path = _node_file_path(item.get("node_id", ""))
                item["slice"] = _infer_slice_from_path(node_path)
                collected.append(item)

    # Stage A
    for name, path in slices:
        if Path(path).exists():
            res = run_context(path, query, budget=stage_a_budget, intent=intent)
            results[name] = res
            for item in res.get("snippets", []):
                item["slice"] = name
                collected.append(item)

    # Stage B only for missing required roles
    missing = _missing_required_slices(
        collected,
        slices,
        query,
        include_tests=include_tests,
        pin=pin,
    )

    for name, path in slices:
        if name in missing and Path(path).exists():
            res = run_context(path, query, budget=stage_b_budget, intent=intent)
            results[f"{name}_retry"] = res
            for item in res.get("snippets", []):
                item["slice"] = name
                collected.append(item)

    deduped = _dedupe_by_file(collected)
    required_slices = {
        name
        for name, _ in slices
        if _required_roles_for_slice(
            name,
            query,
            include_tests=include_tests,
            pin=pin,
            slice_names={n for n, _ in slices},
        )
    }
    missing_after = _missing_required_slices(
        deduped,
        slices,
        query,
        include_tests=include_tests,
        pin=pin,
    )
    effective_max = _expanded_slice_budget(max_total, missing_count=len(missing_after), required_count=len(required_slices))
    trimmed = _trim_to_budget(deduped, max_total=effective_max, required_slices=required_slices)

    return {
        "query": query,
        "profile": profile,
        "mode": "normal",
        "stage_a_budget": stage_a_budget,
        "stage_b_budget": stage_b_budget,
        "max_total_tokens": max_total,
        "intent": intent,
        "results": results,
        "snippets": trimmed,
        "token_estimate": _total_tokens(trimmed),
        "selected_slices": [name for name, _ in slices],
        "missing_required_slices": sorted(missing),
        "missing_required_slices_after": sorted(missing_after),
    }














