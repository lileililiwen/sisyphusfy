"""Durable iteration loop service."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from sisyphusfy.adapters import (
    AdapterConfig,
    AdapterError,
    AgentAdapter,
    ModelChainExhausted,
    resolve_adapter,
    try_fallback,
)
from sisyphusfy.hooks import (
    CompletionPipelineResult,
    HookConfig,
    run_completion_pipeline,
)
from sisyphusfy.runner import run_agent


class LoopStopReason(str, Enum):
    COMPLETE = "complete"
    MAX_ITERATIONS = "max_iterations"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    UNCHANGED_STATE = "unchanged_state"
    VERIFICATION_FAILED = "verification_failed"
    MODELS_EXHAUSTED = "models_exhausted"
    ADAPTER_ERROR = "adapter_error"


@runtime_checkable
class CompletionStrategy(Protocol):
    def has_work(self, task_path: str) -> bool: ...


class MarkdownCheckboxCompletion:
    """All checkboxes checked means complete."""

    def has_work(self, task_path: str) -> bool:
        content = Path(task_path).read_text()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [ ]"):
                return True
        return False


class ExternalCommandCompletion:
    """Exit 0 from check command means complete."""

    def __init__(self, check_command: list[str]) -> None:
        self.check_command = check_command

    def has_work(self, task_path: str) -> bool:
        proc = subprocess.run(
            self.check_command,
            capture_output=True,
            timeout=30,
            check=False,
        )
        return proc.returncode != 0


BLOCKED_MARKERS = ("NEED_PERMISSION", "BLOCKED", "permission", "blocked")


@dataclass
class LoopConfig:
    agent_command: list[str]
    working_directory: str = "."
    task_path: str = "task.md"
    handoff_path: str | None = None
    prompt_template: str = ""
    verification_command: list[str] | None = None
    verification_timeout: float = 30.0
    agent_timeout: float = 60.0
    max_iterations: int = 10
    max_run_records: int = 50
    completion_strategy: CompletionStrategy | None = None
    adapter_config: AdapterConfig | None = None
    model_chain: list[str] = field(default_factory=list)
    completion_hooks: list[HookConfig] = field(default_factory=list)
    dry_run: bool = False


@dataclass
class RunRecord:
    iteration: int
    result: object
    prompt: str = ""


@dataclass
class LoopResult:
    stop_reason: LoopStopReason
    iterations: int
    run_records: list[RunRecord] = field(default_factory=list)
    final_task_path: str = ""
    final_handoff_path: str | None = None
    model_attempts: list[str] = field(default_factory=list)
    adapter_error: str | None = None
    completion_pipeline_result: CompletionPipelineResult | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "stop_reason": self.stop_reason.value,
            "iterations": self.iterations,
            "run_records": [
                {
                    "iteration": r.iteration,
                    "result": r.result.to_dict() if hasattr(r.result, "to_dict") else {},
                }
                for r in self.run_records
            ],
            "final_task_path": self.final_task_path,
            "final_handoff_path": self.final_handoff_path,
        }
        if self.model_attempts:
            d["model_attempts"] = self.model_attempts
        if self.adapter_error:
            d["adapter_error"] = self.adapter_error
        if self.completion_pipeline_result:
            d["completion_pipeline_result"] = self.completion_pipeline_result.to_dict()
        return d


def _snapshot(*paths: str) -> dict[str, str]:
    snap: dict[str, str] = {}
    for p in paths:
        if p and Path(p).exists():
            snap[p] = Path(p).read_text()
    return snap


def _changed(before: dict[str, str], after: dict[str, str]) -> bool:
    return before != after


def _is_blocked(result: object) -> bool:
    stderr = getattr(result, "stderr", "") or ""
    return any(marker.lower() in stderr.lower() for marker in BLOCKED_MARKERS)


def _render_prompt(template: str, **kwargs: str) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def _run_iteration(
    adapter: AgentAdapter | None,
    agent_command: list[str],
    working_directory: str,
    prompt: str,
    timeout: float,
    model: str | None = None,
) -> object:
    env: dict[str, str] = {}
    if model:
        env["AGENT_MODEL"] = model

    if adapter is not None:
        cmd = adapter.build_command(working_directory, prompt)
        extra_args = agent_command[1:] if len(agent_command) > 1 else []
        cmd.extend(extra_args)
        if model and adapter.supports_model(model) and "--model" not in cmd:
                idx = None
                for i, arg in enumerate(cmd):
                    if arg in ("--model", "-m"):
                        idx = i
                        break
                if idx is not None:
                    cmd[idx + 1] = model
                else:
                    cmd.extend(["--model", model])
    else:
        cmd = list(agent_command)
    return run_agent(
        cmd,
        working_directory=working_directory,
        prompt=prompt,
        timeout=timeout,
        env=env if env else None,
    )


def run_loop(config: LoopConfig) -> LoopResult:
    task_path = str(Path(config.task_path).resolve())
    handoff_path = str(Path(config.handoff_path).resolve()) if config.handoff_path else None

    adapter: AgentAdapter | None = None
    if config.adapter_config is not None:
        try:
            adapter = resolve_adapter(config.adapter_config, agent_command=config.agent_command)
        except AdapterError as exc:
            return LoopResult(
                stop_reason=LoopStopReason.ADAPTER_ERROR,
                iterations=0,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                adapter_error=str(exc),
            )

    if config.completion_strategy and not config.completion_strategy.has_work(task_path):
        pipeline_result = None
        if config.completion_hooks:
            pipeline_result = run_completion_pipeline(config.completion_hooks, dry_run=config.dry_run)
        return LoopResult(
            stop_reason=LoopStopReason.COMPLETE,
            iterations=0,
            final_task_path=task_path,
            final_handoff_path=handoff_path,
            completion_pipeline_result=pipeline_result,
        )

    run_records: list[RunRecord] = []
    prev_state = _snapshot(task_path, handoff_path)
    all_model_attempts: list[str] = []

    for i in range(1, config.max_iterations + 1):
        prompt = _render_prompt(
            config.prompt_template,
            task_path=task_path,
            handoff_path=handoff_path or "",
        )

        def _run_with_model(model: str | None = None, p: str = prompt) -> object:
            return _run_iteration(
                adapter,
                config.agent_command,
                config.working_directory,
                p,
                config.agent_timeout,
                model=model,
            )

        if config.model_chain:
            fallback_adapter = adapter or _make_generic(config.agent_command)
            try:
                result, attempts = try_fallback(
                    fallback_adapter,
                    config.model_chain,
                    config.working_directory,
                    prompt,
                    _run_with_model,
                )
                all_model_attempts.extend(attempts)
            except ModelChainExhausted as exc:
                return LoopResult(
                    stop_reason=LoopStopReason.MODELS_EXHAUSTED,
                    iterations=i,
                    run_records=run_records,
                    final_task_path=task_path,
                    final_handoff_path=handoff_path,
                    model_attempts=exc.attempts,
                )
        else:
            result = _run_with_model(model=adapter.model if adapter else None)

        rec = RunRecord(iteration=i, result=result, prompt=prompt)
        run_records.append(rec)

        if len(run_records) > config.max_run_records:
            run_records = run_records[-config.max_run_records:]

        if result.timed_out:
            return LoopResult(
                stop_reason=LoopStopReason.TIMEOUT,
                iterations=i,
                run_records=run_records,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                model_attempts=all_model_attempts,
            )

        if _is_blocked(result):
            return LoopResult(
                stop_reason=LoopStopReason.BLOCKED,
                iterations=i,
                run_records=run_records,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                model_attempts=all_model_attempts,
            )

        if config.completion_strategy and not config.completion_strategy.has_work(task_path):
            pipeline_result = None
            if config.completion_hooks:
                pipeline_result = run_completion_pipeline(config.completion_hooks, dry_run=config.dry_run)
            return LoopResult(
                stop_reason=LoopStopReason.COMPLETE,
                iterations=i,
                run_records=run_records,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                model_attempts=all_model_attempts,
                completion_pipeline_result=pipeline_result,
            )

        if config.verification_command:
            vr = run_agent(
                config.verification_command,
                working_directory=config.working_directory,
                timeout=config.verification_timeout,
            )
            if vr.timed_out:
                return LoopResult(
                    stop_reason=LoopStopReason.TIMEOUT,
                    iterations=i,
                    run_records=run_records,
                    final_task_path=task_path,
                    final_handoff_path=handoff_path,
                    model_attempts=all_model_attempts,
                )
            if vr.classification.value != "success":
                return LoopResult(
                    stop_reason=LoopStopReason.VERIFICATION_FAILED,
                    iterations=i,
                    run_records=run_records,
                    final_task_path=task_path,
                    final_handoff_path=handoff_path,
                    model_attempts=all_model_attempts,
                )

        curr_state = _snapshot(task_path, handoff_path)
        if not _changed(prev_state, curr_state):
            return LoopResult(
                stop_reason=LoopStopReason.UNCHANGED_STATE,
                iterations=i,
                run_records=run_records,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                model_attempts=all_model_attempts,
            )
        prev_state = curr_state

    return LoopResult(
        stop_reason=LoopStopReason.MAX_ITERATIONS,
        iterations=config.max_iterations,
        run_records=run_records,
        final_task_path=task_path,
        final_handoff_path=handoff_path,
        model_attempts=all_model_attempts,
    )


def _make_generic(command: list[str]) -> AgentAdapter:
    from sisyphusfy.adapters import GenericCommandAdapter
    return GenericCommandAdapter(command=command)
