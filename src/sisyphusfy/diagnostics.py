"""Local diagnostic logs for managed subprocesses.

Verification, agent, hook, and workflow output can be large and may carry
project-specific details, so structured results keep only bounded metadata.
The complete streams are written to a local log file that the user can
inspect deliberately. One shared log directory holds every component, and
one shared retention policy prunes the oldest files first.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from sisyphusfy.result import RunResult, format_command

# Log location inside the project directory: <project>/.sisyphusfy/logs/
LOG_ROOT = ".sisyphusfy"
LOG_SUBDIR = "logs"

# Retention bound: repeated loops must not grow the log directory without limit.
DEFAULT_RETENTION = 20

# Bounded metadata kept in structured results; the log file keeps everything.
MAX_OUTPUT_CHARS = 2000

# Backwards-compatible alias for verification logs.
LOG_PREFIX = "verification-"
LOG_SUFFIX = ".log"

# Default in-memory bound applied by the subprocess execution primitive.
DEFAULT_MAX_OUTPUT_BYTES = 65536


def subprocess_log_dir(project_dir: str | Path) -> Path:
    """Return the diagnostic log directory for a project.

    All managed subprocesses (agent, verify, hook, workflow) share this
    directory; their files are differentiated by a component prefix.
    """
    return Path(project_dir).resolve() / LOG_ROOT / LOG_SUBDIR


def make_run_id(now: float | None = None) -> str:
    """Return a stable identifier for one loop run."""
    stamp = time.strftime("%Y%m%dT%H%M%S", time.localtime(time.time() if now is None else now))
    return f"{stamp}-{os.getpid()}"


def subprocess_log_path(
    project_dir: str | Path,
    component: str,
    run_id: str,
    *,
    iteration: int | None = None,
) -> Path:
    """Return the diagnostic log path for a managed subprocess.

    The ``component`` names the caller (``"agent"``, ``"verify"``, ``"hook"``,
    ``"workflow"``); ``run_id`` ties logs to a loop run; ``iteration`` is
    optional so a single one-shot hook invocation can use a flat filename.
    """
    suffix = f"-i{iteration}" if iteration is not None else ""
    return subprocess_log_dir(project_dir) / f"{component}-{run_id}{suffix}{LOG_SUFFIX}"


def verification_log_path(project_dir: str | Path, run_id: str, iteration: int) -> Path:
    """Return the verification log path identifying a run and iteration."""
    return subprocess_log_path(
        project_dir, component="verification", run_id=run_id, iteration=iteration
    )


def verification_log_dir(project_dir: str | Path) -> Path:
    """Return the diagnostic log directory for a project.

    Retained for backwards compatibility; new callers should use
    :func:`subprocess_log_dir` directly.
    """
    return subprocess_log_dir(project_dir)


def bound_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    """Return bounded text and whether it was truncated."""
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _render(result: RunResult) -> str:
    lines = [
        f"command: {format_command(result.command)}",
        f"working directory: {result.working_directory}",
        f"exit status: {result.exit_status}",
        f"classification: {result.classification.value}",
        f"timed out: {'yes' if result.timed_out else 'no'}",
        f"duration: {result.duration_ms}ms",
        f"truncated: {'yes' if result.truncated else 'no'}",
        "",
        "--- stdout ---",
        result.stdout or "",
        "--- stderr ---",
        result.stderr or "",
    ]
    if result.error:
        lines.append("--- error ---")
        lines.append(result.error)
    return "\n".join(lines) + "\n"


def prune_subprocess_logs(log_dir: Path, retention: int = DEFAULT_RETENTION) -> None:
    """Keep only the newest ``retention`` log files across every component.

    All ``*.log`` files in ``log_dir`` are sorted by mtime, then the oldest
    are removed until the directory holds at most ``retention`` files. A
    ``retention`` of zero or less disables retention.
    """
    if retention <= 0:
        return
    logs = [path for path in log_dir.glob(f"*{LOG_SUFFIX}") if path.is_file()]
    if len(logs) <= retention:
        return
    logs.sort(key=lambda path: (path.stat().st_mtime, path.name))
    for path in logs[: len(logs) - retention]:
        try:
            path.unlink()
        except OSError:
            continue


def prune_verification_logs(log_dir: Path, retention: int = DEFAULT_RETENTION) -> None:
    """Keep only the newest ``retention`` verification logs.

    Retained for backwards compatibility; delegates to the unified
    :func:`prune_subprocess_logs` so the whole directory stays bounded.
    """
    prune_subprocess_logs(log_dir, retention)


def write_subprocess_log(
    project_dir: str | Path,
    *,
    component: str,
    run_id: str,
    result: RunResult,
    iteration: int | None = None,
    retention: int = DEFAULT_RETENTION,
) -> Path:
    """Write a managed subprocess's full streams to a local log file.

    Only fields that describe the invocation are written; environment
    values and prompts are never recorded. The log is named after the
    component so the loop, hooks, workflow, and verification each have
    their own files inside one shared directory.
    """
    log_dir = subprocess_log_dir(project_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = subprocess_log_path(
        project_dir, component=component, run_id=run_id, iteration=iteration
    )
    path.write_text(_render(result), encoding="utf-8", errors="replace")
    prune_subprocess_logs(log_dir, retention)
    return path


def write_verification_log(
    project_dir: str | Path,
    run_id: str,
    iteration: int,
    result: RunResult,
    retention: int = DEFAULT_RETENTION,
) -> Path:
    """Write the full verification streams to a local log and return its path.

    Retained for backwards compatibility; delegates to
    :func:`write_subprocess_log` with ``component="verification"`` and the
    given iteration.
    """
    return write_subprocess_log(
        project_dir,
        component="verification",
        run_id=run_id,
        result=result,
        iteration=iteration,
        retention=retention,
    )


def read_verification_log(path: str | Path) -> str | None:
    """Return the saved diagnostics, or None when the log is gone."""
    log_path = Path(path)
    if not log_path.is_file():
        return None
    return log_path.read_text(encoding="utf-8", errors="replace")
