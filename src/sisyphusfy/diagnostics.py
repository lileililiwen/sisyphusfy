"""Local diagnostic logs for verification output.

Verification output can be large and may contain project-specific details, so
results keep only bounded metadata. The complete streams are written to a local
log file that the user can inspect deliberately.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from sisyphusfy.result import RunResult

# Log location inside the project directory: <project>/.sisyphusfy/logs/
LOG_ROOT = ".sisyphusfy"
LOG_SUBDIR = "logs"

# Retention bound: repeated loops must not grow the log directory without limit.
DEFAULT_RETENTION = 20

# Bounded metadata kept in structured results; the log file keeps everything.
MAX_OUTPUT_CHARS = 2000

LOG_PREFIX = "verification-"
LOG_SUFFIX = ".log"


def verification_log_dir(project_dir: str | Path) -> Path:
    """Return the diagnostic log directory for a project."""
    return Path(project_dir).resolve() / LOG_ROOT / LOG_SUBDIR


def make_run_id(now: float | None = None) -> str:
    """Return a stable identifier for one loop run."""
    stamp = time.strftime("%Y%m%dT%H%M%S", time.localtime(time.time() if now is None else now))
    return f"{stamp}-{os.getpid()}"


def verification_log_path(project_dir: str | Path, run_id: str, iteration: int) -> Path:
    """Return the log path identifying a run and iteration."""
    return verification_log_dir(project_dir) / f"{LOG_PREFIX}{run_id}-i{iteration}{LOG_SUFFIX}"


def bound_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    """Return bounded text and whether it was truncated."""
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _render(result: RunResult) -> str:
    lines = [
        f"command: {' '.join(result.command)}",
        f"working directory: {result.working_directory}",
        f"exit status: {result.exit_status}",
        f"classification: {result.classification.value}",
        f"timed out: {'yes' if result.timed_out else 'no'}",
        f"duration: {result.duration_ms}ms",
        "",
        "--- stdout ---",
        result.stdout or "",
        "--- stderr ---",
        result.stderr or "",
    ]
    return "\n".join(lines) + "\n"


def prune_verification_logs(log_dir: Path, retention: int = DEFAULT_RETENTION) -> None:
    """Keep only the newest `retention` verification logs."""
    if retention <= 0:
        return
    logs = [
        path
        for path in log_dir.glob(f"{LOG_PREFIX}*{LOG_SUFFIX}")
        if path.is_file()
    ]
    if len(logs) <= retention:
        return
    logs.sort(key=lambda path: (path.stat().st_mtime, path.name))
    for path in logs[: len(logs) - retention]:
        try:
            path.unlink()
        except OSError:
            continue


def write_verification_log(
    project_dir: str | Path,
    run_id: str,
    iteration: int,
    result: RunResult,
    retention: int = DEFAULT_RETENTION,
) -> Path:
    """Write the full verification streams to a local log and return its path.

    Only fields that describe the invocation are written; environment values and
    prompts are never recorded.
    """
    log_dir = verification_log_dir(project_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = verification_log_path(project_dir, run_id, iteration)
    path.write_text(_render(result), encoding="utf-8", errors="replace")
    prune_verification_logs(log_dir, retention)
    return path


def read_verification_log(path: str | Path) -> str | None:
    """Return the saved diagnostics, or None when the log is gone."""
    log_path = Path(path)
    if not log_path.is_file():
        return None
    return log_path.read_text(encoding="utf-8", errors="replace")
