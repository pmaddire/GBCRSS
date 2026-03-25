"""Coverage.py JSON report loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CoverageFileRecord:
    """Coverage record for a single file."""

    path: str
    executed_lines: tuple[int, ...]
    missing_lines: tuple[int, ...]
    percent_covered: float
    num_statements: int
    num_branches: int
    num_partial_branches: int


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """Loaded coverage report."""

    files: tuple[CoverageFileRecord, ...]


def load_coverage_json(path: str | Path) -> CoverageReport:
    """Load Coverage.py JSON report from disk."""
    report_path = Path(path)
    if not report_path.exists():
        return CoverageReport(files=())

    data = json.loads(report_path.read_text(encoding="utf-8"))
    files_data = data.get("files", {})

    records: list[CoverageFileRecord] = []
    for file_path, entry in files_data.items():
        summary = entry.get("summary", {})
        records.append(
            CoverageFileRecord(
                path=Path(file_path).as_posix(),
                executed_lines=tuple(entry.get("executed_lines", [])),
                missing_lines=tuple(entry.get("missing_lines", [])),
                percent_covered=float(summary.get("percent_covered", 0.0)),
                num_statements=int(summary.get("num_statements", 0)),
                num_branches=int(summary.get("num_branches", 0)),
                num_partial_branches=int(summary.get("num_partial_branches", 0)),
            )
        )

    records.sort(key=lambda r: r.path)
    return CoverageReport(files=tuple(records))