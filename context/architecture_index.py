"""Build and maintain architecture index data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .architecture_parser import ArchitectureDoc


_EXCLUDED_DIRS = {".git", ".gcie", ".venv", "node_modules", "__pycache__"}
_CODE_EXTENSIONS = {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx"}
_CORE_HINTS = {
    "router",
    "routing",
    "fallback",
    "context",
    "slicer",
    "architecture",
    "validation",
    "mode",
    "confidence",
}
_CORE_DIRS = {"context", "router", "routing"}
_CORE_EXCLUDED_DIRS = {"tests", "test"}


def compute_repo_fingerprint(repo_path: Path) -> dict:
    """Compute a lightweight fingerprint for detecting structural changes."""
    top_level_dirs = []
    file_count = 0

    for child in repo_path.iterdir():
        if child.is_dir() and child.name not in _EXCLUDED_DIRS:
            top_level_dirs.append(child.name)

    for path in repo_path.rglob("*"):
        if path.is_dir():
            if path.name in _EXCLUDED_DIRS:
                continue
        if path.is_file() and path.suffix.lower() in _CODE_EXTENSIONS:
            if any(part in _EXCLUDED_DIRS for part in path.parts):
                continue
            file_count += 1

    return {
        "top_level_dirs": sorted(top_level_dirs),
        "code_file_count": file_count,
    }


def _is_core_infrastructure(path: Path) -> bool:
    lowered = path.as_posix().lower()
    parts = {part.lower() for part in path.parts}
    if parts & _CORE_EXCLUDED_DIRS:
        return False
    if parts & _CORE_DIRS:
        return True
    return any(hint in lowered for hint in _CORE_HINTS)


def _discover_core_infrastructure(repo_path: Path) -> list[str]:
    core_files: list[str] = []
    for path in repo_path.rglob("*"):
        if path.is_dir():
            if path.name in _EXCLUDED_DIRS:
                continue
        if not path.is_file() or path.suffix.lower() not in _CODE_EXTENSIONS:
            continue
        if any(part in _EXCLUDED_DIRS for part in path.parts):
            continue
        if _is_core_infrastructure(path):
            core_files.append(path.relative_to(repo_path).as_posix())
    return sorted(set(core_files))


def build_architecture_index(doc: ArchitectureDoc, repo_path: Path) -> dict:
    """Build an index structure from parsed architecture data."""
    subsystems = []
    file_map: dict[str, list[str]] = {}

    for subsystem in doc.subsystems or []:
        subsystems.append(
            {
                "name": subsystem.name,
                "purpose": subsystem.purpose,
                "status": subsystem.status,
                "key_files": subsystem.key_files or [],
                "interfaces": subsystem.interfaces or [],
                "depends_on": subsystem.depends_on or [],
                "used_by": subsystem.used_by or [],
                "failure_modes": subsystem.failure_modes or [],
                "notes": subsystem.notes or [],
            }
        )
        for path in subsystem.key_files or []:
            file_map.setdefault(path, []).append(subsystem.name)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_fingerprint": compute_repo_fingerprint(repo_path),
        "subsystems": subsystems,
        "file_map": file_map,
        "core_infrastructure": _discover_core_infrastructure(repo_path),
    }


def write_architecture_index(path: Path, index_data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index_data, indent=2), encoding="utf-8")


def load_architecture_index(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def has_structural_change(repo_path: Path, index_data: dict) -> bool:
    """Detect whether the repo has structural changes since last index."""
    current = compute_repo_fingerprint(repo_path)
    previous = index_data.get("repo_fingerprint", {})

    if set(current.get("top_level_dirs", [])) != set(previous.get("top_level_dirs", [])):
        return True

    prev_count = previous.get("code_file_count", 0)
    curr_count = current.get("code_file_count", 0)
    if prev_count == 0:
        return False
    delta = abs(curr_count - prev_count) / max(prev_count, 1)
    return delta >= 0.15


def _replace_section(text: str, section_title: str, new_body: str) -> str:
    heading = f"## {section_title}"
    if heading not in text:
        return text.rstrip() + f"\n\n{heading}\n{new_body}\n"

    parts = text.split(heading)
    before = parts[0].rstrip()
    after = heading.join(parts[1:])
    remainder = after.split("\n## ", 1)
    tail = ""
    if len(remainder) == 2:
        tail = "\n## " + remainder[1]
    return f"{before}\n\n{heading}\n{new_body}\n{tail}".strip() + "\n"


def refresh_architecture_if_needed(
    repo_path: Path,
    architecture_path: Path,
    index_path: Path,
) -> bool:
    """Refresh architecture artifacts when structural changes are detected."""
    index_data = load_architecture_index(index_path)
    if index_data is None:
        return False

    if not has_structural_change(repo_path, index_data):
        if not index_data.get("core_infrastructure"):
            index_data["core_infrastructure"] = _discover_core_infrastructure(repo_path)
            index_data["generated_at"] = datetime.now(timezone.utc).isoformat()
            write_architecture_index(index_path, index_data)
            return True
        return False

    if architecture_path.exists():
        text = architecture_path.read_text(encoding="utf-8")
        fingerprint = compute_repo_fingerprint(repo_path)
        active = "\n".join(f"- {name}" for name in fingerprint.get("top_level_dirs", []))
        updated = _replace_section(text, "Active Work Areas", active)
        architecture_path.write_text(updated, encoding="utf-8")

    index_data["repo_fingerprint"] = compute_repo_fingerprint(repo_path)
    index_data["generated_at"] = datetime.now(timezone.utc).isoformat()
    index_data["core_infrastructure"] = _discover_core_infrastructure(repo_path)
    write_architecture_index(index_path, index_data)
    return True


