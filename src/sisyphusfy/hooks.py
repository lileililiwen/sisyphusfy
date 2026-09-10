"""Optional completion hooks for archive and commit."""

from __future__ import annotations

import glob
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from sisyphusfy.diagnostics import subprocess_log_dir
from sisyphusfy.result import Classification
from sisyphusfy.runner import run_command

# Bounded time for the staging subprocess. A run that hangs is a hard failure
# (the hook reports it and does not run the commit command).
STAGE_TIMEOUT_SECONDS = 30.0

# Bounded time for the hook's own command (e.g. `git commit`, `openspec archive`).
HOOK_TIMEOUT_SECONDS = 30.0


class HookType(str, Enum):
    ARCHIVE = "archive"
    COMMIT = "commit"


class HookStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"


class PathEscapeError(Exception):
    pass


@dataclass
class HookResult:
    hook_type: HookType
    status: HookStatus
    command: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "hook_type": self.hook_type.value,
            "status": self.status.value,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class HookConfig:
    hook_type: HookType
    command: list[str] = field(default_factory=list)
    working_directory: str = "."
    allowed_files: list[str] = field(default_factory=list)
    require_confirmation: bool = False
    enabled: bool = False


@dataclass
class CompletionPipelineResult:
    hooks: list[HookResult] = field(default_factory=list)
    stopped_early: bool = False

    def to_dict(self) -> dict:
        return {
            "hooks": [h.to_dict() for h in self.hooks],
            "stopped_early": self.stopped_early,
        }


def _canonicalize_and_validate(
    allowed_files: list[str],
    working_directory: str,
) -> list[str]:
    """Canonicalize allowed file paths and reject escapes."""
    cwd = Path(working_directory).resolve()
    canonical: list[str] = []
    for pattern in allowed_files:
        raw = cwd / pattern
        resolved = raw.resolve()
        try:
            resolved.relative_to(cwd)
        except ValueError:
            raise PathEscapeError(
                f"allowed path escapes working directory: {pattern!r} "
                f"resolves to {resolved}"
            )
        matched = glob.glob(str(resolved))
        if not matched:
            matched = glob.glob(str(raw))
        for match in matched:
            m = Path(match).resolve()
            try:
                m.relative_to(cwd)
            except ValueError:
                raise PathEscapeError(
                    f"allowed path escapes working directory: {pattern!r} "
                    f"resolves to {m}"
                )
            canonical.append(str(m))
    return canonical


def _stage_files(
    files: list[str], working_directory: str
) -> tuple[bool, str, str]:
    """Stage only the given files using `git add` and return the outcome.

    Returns ``(ok, stdout, stderr)``. The call is bounded by a timeout and
    considered failed when ``git add`` exits non-zero. A non-empty stderr is
    preserved on failure so the operator can see why staging was rejected.
    """
    if not files:
        return True, "", ""
    try:
        proc = subprocess.run(
            ["git", "add", "--", *files],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=STAGE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"git add timed out after {STAGE_TIMEOUT_SECONDS}s"
    except FileNotFoundError:
        return False, "", "git executable not found on PATH"
    except OSError as exc:
        return False, "", str(exc)
    if proc.returncode != 0:
        return False, proc.stdout, proc.stderr or f"git add exited with {proc.returncode}"
    return True, proc.stdout, proc.stderr


def _existing_staged_paths(working_directory: str) -> list[str]:
    """Return the pre-staged paths reported by `git diff --cached --name-only`.

    The output uses repository-relative paths. An empty list means the index
    has nothing staged; a non-zero exit (for example, no repository) is treated
    as "no staged paths" so a missing Git or a non-repository workspace does
    not block unrelated callers.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=STAGE_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line]


def _unrelated_staged_paths(
    staged: list[str], allowed: list[str], working_directory: str
) -> list[str]:
    """Return staged paths that are not inside the canonicalized allowlist.

    A pre-staged path is unrelated when its canonical absolute form is not
    matched by any canonical allowed file. The check treats the working
    directory as the trust boundary: staged paths that do not resolve inside
    the working directory are always treated as unrelated so the hook fails
    closed.
    """
    if not staged:
        return []
    cwd = Path(working_directory).resolve()
    allowed_resolved: set[str] = set()
    for path in allowed:
        try:
            allowed_resolved.add(str(Path(path).resolve()))
        except OSError:
            continue

    unrelated: list[str] = []
    for raw in staged:
        candidate = (cwd / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            candidate.relative_to(cwd)
        except ValueError:
            unrelated.append(raw)
            continue
        if str(candidate) not in allowed_resolved:
            unrelated.append(raw)
    return unrelated


def run_hook(config: HookConfig, dry_run: bool = False) -> HookResult:
    if not config.enabled:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.SKIPPED,
            error="hook disabled",
        )

    if not config.command:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.SKIPPED,
            error="no command configured",
        )

    if config.hook_type == HookType.COMMIT and not config.allowed_files:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.SKIPPED,
            error="commit hook requires explicit allowed_files; refusing to stage the whole workspace",
        )

    if dry_run:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.DRY_RUN,
            command=config.command,
        )

    if config.hook_type == HookType.COMMIT:
        try:
            staged = _canonicalize_and_validate(config.allowed_files, config.working_directory)
        except PathEscapeError as exc:
            return HookResult(
                hook_type=config.hook_type,
                status=HookStatus.FAILURE,
                command=config.command,
                error=str(exc),
            )
        pre_staged = _existing_staged_paths(config.working_directory)
        unrelated = _unrelated_staged_paths(
            pre_staged, staged, config.working_directory
        )
        if unrelated:
            return HookResult(
                hook_type=config.hook_type,
                status=HookStatus.FAILURE,
                command=config.command,
                error=(
                    "refusing to commit: pre-existing index has unrelated "
                    "staged paths: " + ", ".join(sorted(unrelated))
                ),
            )
        ok, _, err = _stage_files(staged, config.working_directory)
        if not ok:
            return HookResult(
                hook_type=config.hook_type,
                status=HookStatus.FAILURE,
                command=config.command,
                stderr=err,
                error=f"failed to stage allowed files: {err.strip()}",
            )

    component = f"hook-{config.hook_type.value}"
    result = run_command(
        config.command,
        working_directory=config.working_directory,
        component=component,
        timeout=HOOK_TIMEOUT_SECONDS,
        log_dir=subprocess_log_dir(config.working_directory),
    )
    classification = result.classification
    if classification == Classification.SUCCESS:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.SUCCESS,
            command=config.command,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    if classification == Classification.COMMAND_NOT_FOUND:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.FAILURE,
            command=config.command,
            error=f"command not found: {config.command[0] if config.command else ''}",
        )
    if classification == Classification.TIMEOUT:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.FAILURE,
            command=config.command,
            error=f"hook timed out after {HOOK_TIMEOUT_SECONDS}s",
        )
    if classification == Classification.INTERRUPTED:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.FAILURE,
            command=config.command,
            error="hook interrupted",
        )
    return HookResult(
        hook_type=config.hook_type,
        status=HookStatus.FAILURE,
        command=config.command,
        stdout=result.stdout,
        stderr=result.stderr,
        error=f"exit code {result.exit_status}",
    )


def run_completion_pipeline(
    hooks: list[HookConfig],
    dry_run: bool = False,
) -> CompletionPipelineResult:
    result = CompletionPipelineResult()
    for hook in hooks:
        hook_result = run_hook(hook, dry_run=dry_run)
        result.hooks.append(hook_result)
        if hook_result.status == HookStatus.FAILURE:
            result.stopped_early = True
            break
    return result
