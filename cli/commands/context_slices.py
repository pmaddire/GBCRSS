"""CLI command: context slices."""

from __future__ import annotations

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

    if slice_name in {"backend", "frontend"}:
        roles.add("implementation")
    if wiring_required:
        if slice_name == "frontend" and "frontend" in slice_names:
            roles.add("wiring")
        elif slice_name == "backend" and "frontend" not in slice_names:
            roles.add("wiring")
    if tests_required and slice_name == "tests":
        roles.add("test")
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
        ),
    )

    if payload.get("mode") == "normal" and payload.get("fallback_reason"):
        direct = run_context(repo, query, budget=max_total * 2, intent=intent, top_k=60)
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
        snippets = _merge_snippets(snippets, extra, max_total=max_total * 2)

        payload = {
            "query": direct.get("query", query),
            "profile": profile_used,
            "mode": "direct",
            "intent": intent,
            "snippets": snippets,
            "token_estimate": _total_tokens(snippets),
            "fallback_reason": payload.get("fallback_reason"),
            "secondary_fallback": "normal_empty",
        }

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
) -> dict:
    repo_path = Path(repo)

    slices = []
    frontend_bias = _frontend_bias(query)
    backend_bias = _backend_bias(query)
    frontend_path = _slice_path(repo, "frontend")
    backend_path = _slice_path(repo, "backend")
    tests_path = _slice_path(repo, "tests")

    if frontend_bias and Path(frontend_path).exists():
        slices.append(("frontend", frontend_path))
    if (backend_bias or not frontend_bias) and Path(backend_path).exists():
        slices.append(("backend", backend_path))
    if _needs_tests(query, include_tests) and Path(tests_path).exists():
        slices.append(("tests", tests_path))

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
    effective_max = max_total if not missing_after else max_total * 4
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
    }















