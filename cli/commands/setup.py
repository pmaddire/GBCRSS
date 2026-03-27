"""One-command repository setup for GCIE."""

from __future__ import annotations

from pathlib import Path

from context.architecture_bootstrap import ensure_initialized

from .index import run_index


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _copy_if_needed(source: Path, target: Path, *, force: bool) -> str:
    if not source.exists():
        return "source_missing"
    if target.exists() and not force:
        return "skipped_existing"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return "written"


def run_setup(
    path: str,
    *,
    force: bool = False,
    include_agent_usage: bool = True,
    include_setup_doc: bool = True,
    run_index_pass: bool = True,
) -> dict:
    """Initialize a repository so GCIE can be used immediately."""
    target = Path(path).resolve()
    target.mkdir(parents=True, exist_ok=True)

    config = ensure_initialized(target)
    gcie_dir = target / ".gcie"

    status: dict[str, object] = {
        "repo": target.as_posix(),
        "gcie_dir": gcie_dir.as_posix(),
        "architecture_initialized": True,
        "files": {},
    }

    source_root = _repo_root()
    copied: dict[str, str] = {}

    if include_agent_usage:
        copied["GCIE_USAGE.md"] = _copy_if_needed(
            source_root / "GCIE_USAGE.md",
            target / "GCIE_USAGE.md",
            force=force,
        )

    if include_setup_doc:
        copied["SETUP_ANY_REPO.md"] = _copy_if_needed(
            source_root / "SETUP_ANY_REPO.md",
            target / "SETUP_ANY_REPO.md",
            force=force,
        )

    status["files"] = copied
    status["context_config"] = config

    if run_index_pass:
        status["index"] = run_index(target.as_posix())
    else:
        status["index"] = {"skipped": True}

    return status
