"""Optional completion hooks for archive and commit."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum


class HookType(str, Enum):
    ARCHIVE = "archive"
    COMMIT = "commit"


class HookStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"


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

    if dry_run:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.DRY_RUN,
            command=config.command,
        )

    try:
        proc = subprocess.run(
            config.command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            cwd=config.working_directory,
        )
        if proc.returncode == 0:
            return HookResult(
                hook_type=config.hook_type,
                status=HookStatus.SUCCESS,
                command=config.command,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.FAILURE,
            command=config.command,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error=f"exit code {proc.returncode}",
        )
    except subprocess.TimeoutExpired:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.FAILURE,
            command=config.command,
            error="hook timed out",
        )
    except OSError as exc:
        return HookResult(
            hook_type=config.hook_type,
            status=HookStatus.FAILURE,
            command=config.command,
            error=str(exc),
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
