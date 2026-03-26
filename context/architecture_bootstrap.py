"""Bootstrap GCIE-managed architecture artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .architecture_index import build_architecture_index, refresh_architecture_if_needed, write_architecture_index
from .architecture_parser import parse_architecture


_DEFAULT_DOC_CANDIDATES = [
    "ARCHITECTURE.md",
    "README.md",
    "PROJECT.md",
    "docs/architecture.md",
    "docs/system_design.md",
    "docs/design.md",
]

_EXCLUDED_DIRS = {".git", ".gcie", ".venv", "node_modules", "__pycache__"}


def find_user_architecture_docs(repo_path: Path) -> list[Path]:
    """Find likely user-managed architecture documents in the repo."""
    docs = []
    for candidate in _DEFAULT_DOC_CANDIDATES:
        path = repo_path / candidate
        if path.exists() and path.is_file():
            docs.append(path)
    return docs


def _summarize_docs(docs: list[tuple[Path, str]]) -> str:
    if not docs:
        return "No user-managed architecture docs were found."

    lines = []
    for path, content in docs:
        excerpt = ""
        for line in content.splitlines():
            if line.strip():
                excerpt = line.strip()
                break
        lines.append(f"- {path.as_posix()}: {excerpt[:120]}")
    return "\n".join(lines)


def _discover_subsystems(repo_path: Path) -> list[tuple[str, list[str]]]:
    subsystems = []
    for child in repo_path.iterdir():
        if not child.is_dir() or child.name in _EXCLUDED_DIRS:
            continue
        key_files = []
        for path in child.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".js", ".jsx", ".ts", ".tsx"}:
                key_files.append(path.relative_to(repo_path).as_posix())
            if len(key_files) >= 5:
                break
        subsystems.append((child.name, key_files))
    return subsystems


def _render_architecture(repo_path: Path, docs: list[tuple[Path, str]]) -> str:
    summary = _summarize_docs(docs)
    subsystems = _discover_subsystems(repo_path)
    active_work = "\n".join(f"- {name}" for name, _ in subsystems) or "- core"

    subsystem_blocks = []
    for name, key_files in subsystems:
        key_lines = "\n".join(f"- {path}" for path in key_files) or "- "
        subsystem_blocks.append(
            "\n".join(
                [
                    f"### Subsystem: {name}",
                    "Purpose: ",
                    "Status: active",
                    "Key Files:",
                    key_lines,
                    "Interfaces:",
                    "- ",
                    "Depends On:",
                    "- ",
                    "Used By:",
                    "- ",
                    "Failure Modes:",
                    "- ",
                    "Notes:",
                    "- ",
                ]
            )
        )

    return "\n".join(
        [
            "# GCIE Architecture",
            "",
            "## Project Summary",
            summary,
            "",
            "## System Stage",
            "unknown",
            "",
            "## Global Constraints",
            "",
            "## Subsystems",
            "",
            "\n\n".join(subsystem_blocks) if subsystem_blocks else "### Subsystem: core\nPurpose: ",
            "",
            "## Data Flow",
            "",
            "## Entry Points",
            "",
            "## Active Work Areas",
            active_work,
            "",
            "## Known Risks",
            "",
        ]
    )


def _write_context_config(config_path: Path, *, architecture_source: str) -> dict:
    config = {
        "architecture_slicer_enabled": True,
        "fallback_to_normal_on_low_confidence": True,
        "confidence_threshold": 0.2,
        "architecture_source": architecture_source,
        "last_bootstrap_time": datetime.now(timezone.utc).isoformat(),
        "last_architecture_update": None,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def ensure_initialized(repo_path: Path) -> dict:
    """Ensure GCIE-managed architecture artifacts exist for the repo."""
    gcie_dir = repo_path / ".gcie"
    architecture_path = gcie_dir / "architecture.md"
    index_path = gcie_dir / "architecture_index.json"
    config_path = gcie_dir / "context_config.json"

    config = None
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            config = None

    if not architecture_path.exists():
        docs = [(path, path.read_text(encoding="utf-8")) for path in find_user_architecture_docs(repo_path)]
        architecture_text = _render_architecture(repo_path, docs)
        gcie_dir.mkdir(parents=True, exist_ok=True)
        architecture_path.write_text(architecture_text, encoding="utf-8")

    if not index_path.exists() and architecture_path.exists():
        parsed = parse_architecture(architecture_path.read_text(encoding="utf-8"))
        index_data = build_architecture_index(parsed, repo_path)
        write_architecture_index(index_path, index_data)

    if config is None:
        config = _write_context_config(config_path, architecture_source=architecture_path.as_posix())

    if refresh_architecture_if_needed(repo_path, architecture_path, index_path):
        config["last_architecture_update"] = datetime.now(timezone.utc).isoformat()
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    return config or {}
