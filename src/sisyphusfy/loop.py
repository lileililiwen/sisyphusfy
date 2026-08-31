"""Durable iteration loop service."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from sisyphusfy.adapters import (
    AdapterConfig,
    AdapterError,
    AgentAdapter,
    AgentError,
    ModelChainExhausted,
    resolve_adapter,
    try_fallback,
)
from sisyphusfy.diagnostics import (
    bound_output,
    make_run_id,
    write_verification_log,
)
from sisyphusfy.hooks import (
    CompletionPipelineResult,
    HookConfig,
    run_completion_pipeline,
)
from sisyphusfy.progress import (
    COMPONENT_AGENT,
    COMPONENT_VERIFY,
    DEFAULT_HEARTBEAT_SECONDS,
    ProgressSink,
    progress_callbacks,
)
from sisyphusfy.result import Classification, RunResult
from sisyphusfy.runner import run_agent
from sisyphusfy.workflows import (
    WorkflowAdapter,
    WorkflowConfig,
    WorkflowError,
    adapter_runs_commands,
    resolve_workflow_adapter,
)


class LoopStopReason(str, Enum):
    COMPLETE = "complete"
    MAX_ITERATIONS = "max_iterations"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"
    BLOCKED = "blocked"
    AGENT_FAILED = "agent_failed"
    UNCHANGED_STATE = "unchanged_state"
    VERIFICATION_FAILED = "verification_failed"
    MODELS_EXHAUSTED = "models_exhausted"
    ADAPTER_ERROR = "adapter_error"
    DRY_RUN = "dry_run"
    COMMAND_NOT_FOUND = "command_not_found"


class CompletionOutcome(str, Enum):
    HAS_WORK = "has_work"
    COMPLETE = "complete"
    DRY_RUN = "dry_run"


class CompletionCheckError(Exception):
    """A completion check command could not be executed."""


@runtime_checkable
class CompletionStrategy(Protocol):
    def has_work(self, task_path: str) -> bool: ...


def completion_strategy_runs_commands(strategy: CompletionStrategy) -> bool:
    """Report whether completion evaluation would execute a subprocess.

    Custom strategies can declare a ``runs_commands`` attribute instead of
    being the built-in external-command strategy.
    """
    if isinstance(strategy, ExternalCommandCompletion):
        return bool(strategy.check_command)
    return bool(getattr(strategy, "runs_commands", False))


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

    def __init__(
        self,
        check_command: list[str],
        timeout: float = 30.0,
        working_directory: str = ".",
        dry_run: bool = False,
    ) -> None:
        self.check_command = check_command
        self.timeout = timeout
        self.working_directory = working_directory
        self.dry_run = dry_run

    def has_work(self, task_path: str) -> bool:
        if self.dry_run:
            return True
        try:
            proc = subprocess.run(
                self.check_command,
                capture_output=True,
                timeout=self.timeout,
                check=False,
                cwd=self.working_directory,
            )
        except FileNotFoundError as exc:
            raise CompletionCheckError(
                f"completion check command not found: {self.check_command[0]}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise CompletionCheckError(
                f"completion check command timed out after {self.timeout}s"
            ) from exc
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
    verification_source: str = "configured"
    verification_detector: str = ""
    agent_timeout: float = 60.0
    max_iterations: int = 10
    max_run_records: int = 50
    completion_strategy: CompletionStrategy | None = None
    adapter_config: AdapterConfig | None = None
    model_chain: list[str] = field(default_factory=list)
    completion_hooks: list[HookConfig] = field(default_factory=list)
    dry_run: bool = False
    workflow_adapter: WorkflowAdapter | None = None
    workflow_config: WorkflowConfig | None = None
    blocked_markers: list[str] = field(default_factory=lambda: list(BLOCKED_MARKERS))
    progress: ProgressSink | None = None
    heartbeat_interval: float = DEFAULT_HEARTBEAT_SECONDS


@dataclass
class RunRecord:
    iteration: int
    result: object
    prompt: str = ""


@dataclass
class VerificationEvidence:
    """Structured evidence for one verification invocation.

    Output is bounded; the complete streams live in the local diagnostic log.
    """

    command: list[str]
    working_directory: str
    exit_status: int | None
    status: str
    timed_out: bool
    duration_ms: float
    source: str = "configured"
    detector: str = ""
    log_path: str | None = None
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "command": list(self.command),
            "source": self.source,
            "detector": self.detector,
            "working_directory": self.working_directory,
            "exit_status": self.exit_status,
            "status": self.status,
            "timed_out": self.timed_out,
            "duration_ms": self.duration_ms,
            "log_path": self.log_path,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
        }


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
    verification: VerificationEvidence | None = None
    agent_evidence: VerificationEvidence | None = None
    agent_error: AgentError | None = None

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
        if self.verification:
            d["verification"] = self.verification.to_dict()
        if self.agent_evidence:
            d["agent_evidence"] = self.agent_evidence.to_dict()
        if self.agent_error:
            d["agent_error"] = self.agent_error.to_dict()
        return d


def _snapshot(*paths: str) -> dict[str, str]:
    snap: dict[str, str] = {}
    for p in paths:
        if p and Path(p).exists():
            snap[p] = Path(p).read_text()
    return snap


def _changed(before: dict[str, str], after: dict[str, str]) -> bool:
    return before != after


def _is_blocked(result: object, markers: list[str] | None = None) -> bool:
    if markers is None:
        markers = list(BLOCKED_MARKERS)
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    combined = stdout + stderr
    return any(marker.lower() in combined.lower() for marker in markers)


DEFAULT_PROMPT_TEMPLATE = (
    "Read {task_path} and any handoff at {handoff_path}. "
    "Implement one task. Update the handoff with what you did and what comes next. "
    "If you are blocked, write a short explanation and stop."
)


def _render_prompt(template: str, **kwargs: str) -> str:
    if not template.strip():
        template = DEFAULT_PROMPT_TEMPLATE
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def _resolve_under(working_directory: str, path: str) -> str:
    """Resolve a configured path against the loop working directory."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    return str((Path(working_directory) / candidate).resolve())


def _scoped_workflow_config(
    config: WorkflowConfig,
    working_directory: str,
    dry_run: bool,
) -> WorkflowConfig:
    """Resolve relative workflow paths and scope commands to the working directory."""
    return replace(
        config,
        task_path=_resolve_under(working_directory, config.task_path) if config.task_path else "",
        state_path=_resolve_under(working_directory, config.state_path) if config.state_path else "",
        change_dir=_resolve_under(working_directory, config.change_dir) if config.change_dir else "",
        working_directory=config.working_directory or working_directory,
        dry_run=config.dry_run or dry_run,
    )


def _scoped_completion_strategy(
    strategy: CompletionStrategy | None,
    working_directory: str,
) -> CompletionStrategy | None:
    """Run an unscoped external completion check in the loop working directory."""
    if isinstance(strategy, ExternalCommandCompletion) and strategy.working_directory in ("", "."):
        return ExternalCommandCompletion(
            check_command=strategy.check_command,
            timeout=strategy.timeout,
            working_directory=working_directory,
            dry_run=strategy.dry_run,
        )
    return strategy


def _hooks_with_directory(
    hooks: list[HookConfig],
    working_directory: str,
) -> list[HookConfig]:
    """Run unscoped hooks in the loop working directory instead of the caller's cwd."""
    return [
        replace(hook, working_directory=working_directory)
        if hook.working_directory in ("", ".")
        else hook
        for hook in hooks
    ]


def _run_iteration(
    adapter: AgentAdapter | None,
    agent_command: list[str],
    working_directory: str,
    prompt: str,
    timeout: float,
    model: str | None = None,
    dry_run: bool = False,
    on_output: Callable[[str], None] | None = None,
    on_heartbeat: Callable[[float, float], None] | None = None,
    heartbeat_interval: float = DEFAULT_HEARTBEAT_SECONDS,
) -> object:
    env: dict[str, str] = {}
    if model:
        env["AGENT_MODEL"] = model

    if adapter is not None:
        cmd = adapter.build_command(working_directory, prompt)
        extra_args = agent_command[1:] if len(agent_command) > 1 else []
        cmd.extend(extra_args)
        if model and adapter.supports_model(model):
            has_model_flag = any(a in ("--model", "-m") for a in cmd)
            if not has_model_flag:
                cmd.extend(["--model", model])
            else:
                for i, arg in enumerate(cmd):
                    if arg in ("--model", "-m"):
                        cmd[i + 1] = model
                        break
    else:
        cmd = list(agent_command)
    return run_agent(
        cmd,
        working_directory=working_directory,
        prompt=prompt,
        timeout=timeout,
        env=env if env else None,
        dry_run=dry_run,
        on_output=on_output,
        on_heartbeat=on_heartbeat,
        heartbeat_interval=heartbeat_interval,
    )


def run_loop(config: LoopConfig) -> LoopResult:
    """Run the loop and attach the evidence from its last verification."""
    evidence: dict[str, VerificationEvidence] = {}
    result = _run_loop(config, evidence)
    if result.verification is None and COMPONENT_VERIFY in evidence:
        result.verification = evidence[COMPONENT_VERIFY]
    return result


def _run_loop(config: LoopConfig, evidence: dict[str, VerificationEvidence]) -> LoopResult:
    working_directory = str(Path(config.working_directory).resolve())
    task_path = _resolve_under(working_directory, config.task_path)
    handoff_path = (
        _resolve_under(working_directory, config.handoff_path) if config.handoff_path else None
    )

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

    workflow_adapter = config.workflow_adapter
    if workflow_adapter is None and config.workflow_config is not None:
        try:
            workflow_adapter = resolve_workflow_adapter(
                _scoped_workflow_config(
                    config.workflow_config, working_directory, config.dry_run
                )
            )
        except WorkflowError as exc:
            return LoopResult(
                stop_reason=LoopStopReason.ADAPTER_ERROR,
                iterations=0,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                adapter_error=f"workflow adapter error: {exc}",
            )

    run_records: list[RunRecord] = []
    all_model_attempts: list[str] = []
    hooks = _hooks_with_directory(config.completion_hooks, working_directory)
    completion_strategy = _scoped_completion_strategy(
        config.completion_strategy, working_directory
    )

    run_id = make_run_id()
    agent_cbs = progress_callbacks(config.progress, COMPONENT_AGENT)
    verify_cbs = progress_callbacks(config.progress, COMPONENT_VERIFY)

    def _record_evidence(
        result: RunResult,
        iteration: int,
        component: str = COMPONENT_VERIFY,
        source: str | None = None,
        detector: str | None = None,
    ) -> VerificationEvidence | None:
        """Persist full diagnostics and retain bounded evidence for the result."""
        if result.classification is Classification.DRY_RUN:
            return None
        stdout, stdout_truncated = bound_output(result.stdout or "")
        stderr, stderr_truncated = bound_output(result.stderr or "")
        log_path: str | None = None
        try:
            log_path = str(write_verification_log(working_directory, run_id, iteration, result))
        except OSError:
            log_path = None
        item = VerificationEvidence(
            command=list(result.command),
            working_directory=result.working_directory,
            exit_status=result.exit_status,
            status=result.classification.value,
            timed_out=result.timed_out,
            duration_ms=result.duration_ms,
            source=source if source is not None else config.verification_source,
            detector=detector if detector is not None else config.verification_detector,
            log_path=log_path,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )
        evidence[component] = item
        return item

    def _agent_stop(
        reason: LoopStopReason,
        iteration: int,
        result: object,
        model_attempts: list[str] | None = None,
        agent_error: AgentError | None = None,
    ) -> LoopResult:
        """Stop after an agent run, keeping the diagnostics for that run."""
        item = _record_evidence(
            result,
            iteration,
            COMPONENT_AGENT,
            source=COMPONENT_AGENT,
            detector="",
        ) if isinstance(result, RunResult) else None
        return LoopResult(
            stop_reason=reason,
            iterations=iteration,
            run_records=run_records,
            final_task_path=task_path,
            final_handoff_path=handoff_path,
            model_attempts=model_attempts if model_attempts is not None else all_model_attempts,
            agent_evidence=item,
            agent_error=agent_error,
        )

    def _run_verification(iteration: int) -> LoopResult | None:
        """Run verification once. Returns a failure result, or None on success."""
        if not config.verification_command:
            return None
        on_output, on_heartbeat = verify_cbs
        vr = run_agent(
            config.verification_command,
            working_directory=working_directory,
            timeout=config.verification_timeout,
            dry_run=config.dry_run,
            on_output=on_output,
            on_heartbeat=on_heartbeat,
            heartbeat_interval=config.heartbeat_interval,
        )
        _record_evidence(vr, iteration)
        if getattr(vr, "interrupted", False):
            return LoopResult(
                stop_reason=LoopStopReason.INTERRUPTED,
                iterations=iteration,
                run_records=run_records,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                model_attempts=all_model_attempts,
            )
        if vr.timed_out:
            return LoopResult(
                stop_reason=LoopStopReason.TIMEOUT,
                iterations=iteration,
                run_records=run_records,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                model_attempts=all_model_attempts,
            )
        if vr.classification is Classification.COMMAND_NOT_FOUND:
            return _command_failure(
                f"verification command not found: {vr.command[0] if vr.command else ''}",
                iteration,
            )
        if vr.classification.value not in ("success", "dry_run"):
            return LoopResult(
                stop_reason=LoopStopReason.VERIFICATION_FAILED,
                iterations=iteration,
                run_records=run_records,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                model_attempts=all_model_attempts,
            )
        return None

    def _evaluate_completion(reload: bool) -> CompletionOutcome:
        """Decide whether work remains without executing commands under dry-run."""
        if completion_strategy is not None:
            if config.dry_run and completion_strategy_runs_commands(completion_strategy):
                return CompletionOutcome.DRY_RUN
            has_work = completion_strategy.has_work(task_path)
        elif workflow_adapter is not None:
            if reload:
                workflow_adapter.reload()
            if config.dry_run and adapter_runs_commands(workflow_adapter):
                return CompletionOutcome.DRY_RUN
            has_work = workflow_adapter.has_work()
        else:
            return CompletionOutcome.HAS_WORK
        return CompletionOutcome.HAS_WORK if has_work else CompletionOutcome.COMPLETE

    def _command_failure(message: str, iteration: int) -> LoopResult:
        return LoopResult(
            stop_reason=LoopStopReason.COMMAND_NOT_FOUND,
            iterations=iteration,
            run_records=run_records,
            final_task_path=task_path,
            final_handoff_path=handoff_path,
            model_attempts=all_model_attempts,
            adapter_error=message,
        )

    def _complete(iteration: int) -> LoopResult:
        pipeline_result = run_completion_pipeline(hooks, dry_run=config.dry_run) if hooks else None
        return LoopResult(
            stop_reason=LoopStopReason.COMPLETE,
            iterations=iteration,
            run_records=run_records,
            final_task_path=task_path,
            final_handoff_path=handoff_path,
            model_attempts=all_model_attempts,
            completion_pipeline_result=pipeline_result,
        )

    try:
        outcome = _evaluate_completion(reload=False)
    except (CompletionCheckError, WorkflowError) as exc:
        return _command_failure(str(exc), 0)
    if outcome is CompletionOutcome.DRY_RUN:
        return LoopResult(
            stop_reason=LoopStopReason.DRY_RUN,
            iterations=0,
            final_task_path=task_path,
            final_handoff_path=handoff_path,
        )
    if outcome is CompletionOutcome.COMPLETE:
        verification_failure = _run_verification(0)
        if verification_failure is not None:
            return verification_failure
        return _complete(0)

    completed_iteration = 0
    try:
        prev_state = _snapshot(task_path, handoff_path)

        for i in range(1, config.max_iterations + 1):
            completed_iteration = i
            prompt = _render_prompt(
                config.prompt_template,
                task_path=task_path,
                handoff_path=handoff_path or "",
            )

            def _run_with_model(model: str | None = None, p: str = prompt) -> object:
                on_output, on_heartbeat = agent_cbs
                return _run_iteration(
                    adapter,
                    config.agent_command,
                    working_directory,
                    p,
                    config.agent_timeout,
                    model=model,
                    dry_run=config.dry_run,
                    on_output=on_output,
                    on_heartbeat=on_heartbeat,
                    heartbeat_interval=config.heartbeat_interval,
                )

            if config.model_chain:
                fallback_adapter = adapter or _make_generic(config.agent_command)
                try:
                    result, attempts = try_fallback(
                        fallback_adapter,
                        config.model_chain,
                        working_directory,
                        prompt,
                        _run_with_model,
                    )
                    all_model_attempts.extend(attempts)
                except ModelChainExhausted as exc:
                    return _agent_stop(
                        LoopStopReason.MODELS_EXHAUSTED,
                        i,
                        exc.last_result,
                        model_attempts=exc.attempts,
                    )
            else:
                result = _run_with_model(model=adapter.model if adapter else None)

            rec = RunRecord(iteration=i, result=result, prompt=prompt)
            run_records.append(rec)

            if len(run_records) > config.max_run_records:
                run_records = run_records[-config.max_run_records:]

            if getattr(result, "classification", None) is Classification.COMMAND_NOT_FOUND:
                missing = result.command[0] if getattr(result, "command", None) else ""
                return _command_failure(f"agent command not found: {missing}", i)

            if getattr(result, "interrupted", False):
                return _agent_stop(LoopStopReason.INTERRUPTED, i, result)

            if result.timed_out:
                return _agent_stop(LoopStopReason.TIMEOUT, i, result)

            if _is_blocked(result, config.blocked_markers):
                return LoopResult(
                    stop_reason=LoopStopReason.BLOCKED,
                    iterations=i,
                    run_records=run_records,
                    final_task_path=task_path,
                    final_handoff_path=handoff_path,
                    model_attempts=all_model_attempts,
                )

            # A non-zero exit is a failed agent run, whether or not a model
            # chain is configured. Reaching this point with a chain means
            # `try_fallback` already judged the failure non-retryable, because
            # an all-retryable chain raises `ModelChainExhausted` above.
            raw_exit = getattr(result, "exit_status", None)
            if raw_exit is not None and raw_exit != 0:
                return _agent_stop(
                    LoopStopReason.AGENT_FAILED,
                    i,
                    result,
                    agent_error=_parse_agent_error(
                        adapter or _make_generic(config.agent_command), result
                    ),
                )

            # Verification runs exactly once per productive iteration and always
            # before completion is accepted or hooks are invoked.
            verification_failure = _run_verification(i)
            if verification_failure is not None:
                return verification_failure

            try:
                outcome = _evaluate_completion(reload=True)
            except (CompletionCheckError, WorkflowError) as exc:
                return _command_failure(str(exc), i)
            if outcome is CompletionOutcome.DRY_RUN:
                return LoopResult(
                    stop_reason=LoopStopReason.DRY_RUN,
                    iterations=i,
                    run_records=run_records,
                    final_task_path=task_path,
                    final_handoff_path=handoff_path,
                    model_attempts=all_model_attempts,
                )
            if outcome is CompletionOutcome.COMPLETE:
                return _complete(i)

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

    except KeyboardInterrupt:
        return LoopResult(
            stop_reason=LoopStopReason.INTERRUPTED,
            iterations=completed_iteration,
            run_records=run_records,
            final_task_path=task_path,
            final_handoff_path=handoff_path,
            model_attempts=all_model_attempts,
        )

    return LoopResult(
        stop_reason=LoopStopReason.MAX_ITERATIONS,
        iterations=config.max_iterations,
        run_records=run_records,
        final_task_path=task_path,
        final_handoff_path=handoff_path,
        model_attempts=all_model_attempts,
    )


def _parse_agent_error(adapter: AgentAdapter, result: object) -> AgentError | None:
    """Ask an adapter for the structured agent error, if it exposes one.

    Third-party adapters written against the earlier protocol have no
    `parse_error`, and an adapter that raises must not take the supervisor
    down. Either case degrades to "no structured error" while the stop reason
    still reflects the non-zero exit status.
    """
    parse = getattr(adapter, "parse_error", None)
    if parse is None:
        return None
    combined = (
        f"{getattr(result, 'stdout', '') or ''}\n"
        f"{getattr(result, 'stderr', '') or ''}"
    )
    try:
        return parse(combined)
    except Exception:  # noqa: BLE001 - a third-party parser must not stop the loop
        return None


def _make_generic(command: list[str]) -> AgentAdapter:
    from sisyphusfy.adapters import GenericCommandAdapter
    return GenericCommandAdapter(command=command)
