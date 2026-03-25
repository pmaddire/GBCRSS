"""Git history miner using GitPython."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from git import Repo
from git.exc import GitCommandError


@dataclass(frozen=True, slots=True)
class FileChange:
    """Single file-level change in a commit."""

    path: str
    change_type: str


@dataclass(frozen=True, slots=True)
class CommitRecord:
    """Normalized commit metadata."""

    hexsha: str
    author: str
    committed_date: int
    summary: str
    files: tuple[FileChange, ...]


def mine_commit_history(repo_path: str | Path, *, max_count: int | None = None) -> tuple[CommitRecord, ...]:
    """Return normalized commit history from a git repository."""
    repo = Repo(Path(repo_path))
    if repo.bare:
        repo.close()
        return ()

    try:
        try:
            commits = list(repo.iter_commits("HEAD", max_count=max_count))
        except (ValueError, GitCommandError):
            # No commits/HEAD yet.
            return ()

        out: list[CommitRecord] = []

        for commit in commits:
            file_changes: list[FileChange] = []

            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit, create_patch=False)
                for diff in diffs:
                    new_path = diff.b_path or diff.a_path or ""
                    file_changes.append(
                        FileChange(
                            path=new_path,
                            change_type=(diff.change_type or "M").upper(),
                        )
                    )
            else:
                for path in commit.stats.files.keys():
                    file_changes.append(FileChange(path=path, change_type="A"))

            out.append(
                CommitRecord(
                    hexsha=commit.hexsha,
                    author=str(commit.author),
                    committed_date=int(commit.committed_date),
                    summary=commit.summary,
                    files=tuple(file_changes),
                )
            )

        return tuple(out)
    finally:
        repo.git.clear_cache()
        repo.close()