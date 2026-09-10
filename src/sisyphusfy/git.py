"""Read-only Git inspection.

This module is the only place that talks to the `git` executable for
status and diff. The loop engine itself stays project-agnostic; the
human CLI uses this adapter when a Git repository is present. All
commands are read-only (`status`, `diff`, `diff --stat`), run with a
bounded timeout, and return a structured snapshot even when Git is
missing or the directory is not a repository. Nothing is staged,
committed, pushed, or otherwise modified.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Bounded time for every Git inspection command. The adapter is read-only
# and the commands are fast, so a short timeout is enough to detect a stuck
# or hung `git` invocation.
DEFAULT_INSPECT_TIMEOUT_SECONDS = 10.0

# Default bound on the unified-diff payload. A diff larger than this is
# truncated; the truncation flag is part of the structured result.
DEFAULT_DIFF_MAX_BYTES = 50_000


class DiffMode(str, Enum):
    """Which diff to read from the repository."""

    UNSTAGED = "unstaged"
    STAGED = "staged"


def _git_command() -> list[str]:
    """Return the `git` argument prefix used for read-only inspection.

    Stored as a module-level list so tests can monkeypatch it
    (for example, to simulate a missing `git`).
    """
    return list(_GIT_COMMAND)


_GIT_COMMAND: list[str] = ["git"]


@dataclass
class StatusEntry:
    """One line from `git status --porcelain`.

    The `status` field carries the two-character porcelain code (for
    example, `" M"`, `"A "`, `"??"`). `path` is the working-tree path
    relative to the repository root.
    """

    status: str
    path: str


@dataclass
class GitInspection:
    """Structured result of one read-only inspection.

    `available` is False when Git is missing, the directory is not a
    repository, or a command times out / errors. The other fields keep
    their documented shape: `branch` and `status_entries` describe the
    working tree, `diff_text` and `stat_text` are the bounded patch
    payloads, and `truncated` reports whether the diff was clipped.
    `error` is set when inspection was attempted but failed.
    """

    available: bool
    reason: str = ""
    branch: str = ""
    status_entries: list[StatusEntry] = field(default_factory=list)
    status_paths: list[str] = field(default_factory=list)
    changed_files: int = 0
    diff_text: str = ""
    stat_text: str = ""
    truncated: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "reason": self.reason,
            "branch": self.branch,
            "status_entries": [
                {"status": e.status, "path": e.path} for e in self.status_entries
            ],
            "status_paths": list(self.status_paths),
            "changed_files": self.changed_files,
            "diff_text": self.diff_text,
            "stat_text": self.stat_text,
            "truncated": self.truncated,
            "error": self.error,
        }


def _run(
    args: list[str],
    working_directory: str,
    timeout: float = DEFAULT_INSPECT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess | None:
    """Run a read-only `git` command and return the completed process.

    Returns None when Git is missing, the command is rejected, the
    subprocess times out, or the working directory does not exist. The
    caller inspects `returncode` to distinguish "no changes" from
    "command failed".
    """
    cmd = _git_command() + args
    try:
        return subprocess.run(
            cmd,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    except subprocess.TimeoutExpired:
        return None


def _git_available() -> bool:
    """Return True when the `git` executable is on PATH."""
    return shutil.which(_git_command()[0]) is not None


def _bounded(text: str, max_bytes: int) -> tuple[str, bool]:
    """Truncate `text` to at most `max_bytes` and report whether it was cut."""
    if max_bytes <= 0:
        return "", True
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text, False
    return encoded[:max_bytes].decode("utf-8", errors="replace"), True


def _parse_status(porcelain: str) -> list[StatusEntry]:
    """Parse `git status --porcelain` into structured entries.

    Renamed/copied paths may include a ` -> ` middle; the destination
    path is what matters for an operator review.
    """
    entries: list[StatusEntry] = []
    for raw in porcelain.splitlines():
        if not raw:
            continue
        # Format: XY <path> (where <path> may start with a rename/copy arrow)
        if len(raw) < 3:
            continue
        code = raw[:2]
        rest = raw[3:].strip()
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1].strip()
        entries.append(StatusEntry(status=code, path=rest))
    return entries


def inspect(
    project_dir: str | Path,
    mode: DiffMode = DiffMode.UNSTAGED,
    stat_only: bool = False,
    max_bytes: int = DEFAULT_DIFF_MAX_BYTES,
    timeout: float = DEFAULT_INSPECT_TIMEOUT_SECONDS,
) -> GitInspection:
    """Return a read-only snapshot of `project_dir`'s Git state.

    The result always carries a structured `available` flag and never
    raises. A non-repository, a missing `git`, a working-directory
    that does not exist, a timed-out command, or any non-zero exit
    becomes an unavailable result with a `reason` so the caller can
    present it without surfacing a stack trace.
    """
    if not _git_available():
        return GitInspection(available=False, reason="git_unavailable")

    path = Path(project_dir).expanduser().resolve()
    if not path.is_dir():
        return GitInspection(available=False, reason="directory_not_found")

    # `git rev-parse --is-inside-work-tree` is the canonical "is this a
    # repo?" probe. Anything else (missing repo, worktree only, sub-module
    # of a parent) becomes a structured unavailable result.
    probe = _run(
        ["rev-parse", "--is-inside-work-tree"], str(path), timeout=timeout
    )
    if probe is None or probe.returncode != 0 or probe.stdout.strip() != "true":
        return GitInspection(available=False, reason="not_a_repository")

    branch = ""
    branch_proc = _run(
        ["rev-parse", "--abbrev-ref", "HEAD"], str(path), timeout=timeout
    )
    if branch_proc is not None and branch_proc.returncode == 0:
        branch = branch_proc.stdout.strip()

    status_proc = _run(
        ["status", "--porcelain", "--untracked-files=normal"],
        str(path),
        timeout=timeout,
    )
    status_entries: list[StatusEntry] = []
    if status_proc is not None and status_proc.returncode == 0:
        status_entries = _parse_status(status_proc.stdout)
    status_paths = [e.path for e in status_entries]
    changed_files = sum(1 for e in status_entries if e.status.strip())

    diff_text = ""
    stat_text = ""
    truncated = False

    if stat_only:
        stat_args = ["diff", "--stat"]
        if mode is DiffMode.STAGED:
            stat_args.append("--cached")
        stat_proc = _run(stat_args, str(path), timeout=timeout)
        if stat_proc is not None and stat_proc.returncode == 0:
            stat_text = stat_proc.stdout.rstrip()
    else:
        diff_args = ["diff"]
        if mode is DiffMode.STAGED:
            diff_args.append("--cached")
        diff_proc = _run(diff_args, str(path), timeout=timeout)
        if diff_proc is not None and diff_proc.returncode == 0:
            diff_text, truncated = _bounded(diff_proc.stdout, max_bytes)

    return GitInspection(
        available=True,
        branch=branch,
        status_entries=status_entries,
        status_paths=status_paths,
        changed_files=changed_files,
        diff_text=diff_text,
        stat_text=stat_text,
        truncated=truncated,
    )
