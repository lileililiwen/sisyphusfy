"""Durable iteration loop service."""

from __future__ import annotations

import subprocess
import sys
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
from sisyphusfy.config import ConfigurationError
from sisyphusfy.context import (
    ContextBudget,
    ContextEstimate,
    ContextTelemetry,
    ExactUsage,
    HandoffCompactor,
    apply_budget_to_prompt,
    estimate_text,
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
    CONTEXT_BUDGET_EXCEEDED = "context_budget_exceeded"


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


@dataclass
class PromptAnswer:
    """The decision captured from an interactive permission prompt.

    ``denied`` ends the iteration with a ``blocked`` result; otherwise ``text``
    (which may be empty, meaning "approved with no extra instruction") is folded
    into the next agent prompt so the loop can continue.
    """

    denied: bool
    text: str = ""


def _read_terminal_answer(blocker: str) -> PromptAnswer:
    """Default interactive prompt: read one line from the terminal.

    Reads from stdin and treats empty input, ``deny``, ``no``, or ``n`` as a
    denial. Any other input is an approval (the text becomes the operator's
    answer). On EOF/error it denies, so a piped run can never hang here -- the
    loop engine still stops with ``blocked`` as in the non-interactive path.
    An empty-input denial is reported explicitly so an accidental Enter can
    never silently abort the run.
    """
    try:
        sys.stderr.write("\n[sisyphusfy] agent is blocked and needs a decision:\n")
        for line in blocker.splitlines() or [blocker]:
            sys.stderr.write(f"  {line}\n")
        sys.stderr.write("approve (or type your answer), or 'deny'/'no' to stop: ")
        sys.stderr.flush()
        raw = sys.stdin.readline()
    except (OSError, EOFError):
        return PromptAnswer(denied=True)
    if not raw:
        return PromptAnswer(denied=True)
    text = raw.strip()
    if not text:
        sys.stderr.write("denied (empty input)\n")
        sys.stderr.flush()
        return PromptAnswer(denied=True)
    if text.lower() in {"deny", "no", "n"}:
        return PromptAnswer(denied=True)
    return PromptAnswer(denied=False, text=text)


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


BLOCKED_MARKERS = ("NEED_PERMISSION", "BLOCKED")


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
    interactive: bool = False
    max_interactive_prompts: int = 3
    prompt_user: Callable[[str], PromptAnswer] | None = _read_terminal_answer
    workspace_evidence: list[str] = field(default_factory=list)
    trust_paths_outside_root: bool = False
    context_budget: ContextBudget | None = None
    compact_handoff: bool = False


@dataclass
class RunRecord:
    iteration: int
    result: object
    prompt: str = ""
    context_estimate: ContextEstimate | None = None
    exact_usage: ExactUsage | None = None


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
    blocked_reason: str | None = None
    context_telemetry: ContextTelemetry | None = None

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
        if self.blocked_reason:
            d["blocked_reason"] = self.blocked_reason
        if self.context_telemetry is not None:
            d["context_telemetry"] = self.context_telemetry.to_dict()
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
    """Return True only when a configured marker matches a whole line.

    Markers are matched against stripped lines from the combined output so
    ordinary prose such as "permission bits" or "blocked reviewer" no longer
    trips the blocked path. Substring search inside a sentence is no longer
    a heuristic.
    """
    if markers is None:
        markers = list(BLOCKED_MARKERS)
    if not markers:
        return False
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    combined = stdout + stderr
    normalised_markers = [m.strip() for m in markers if m and m.strip()]
    if not normalised_markers:
        return False
    for line in combined.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for marker in normalised_markers:
            if stripped == marker or _marker_token_present(stripped, marker):
                return True
    return False


def _marker_token_present(line: str, marker: str) -> bool:
    """Treat the marker as a token-boundary match inside the line.

    Allows ``"NEED_PERMISSION: cannot proceed"`` to match while leaving
    ``"permission bits"`` alone. The marker is wrapped in non-word
    boundaries.
    """
    if marker not in line:
        return False
    idx = 0
    while True:
        pos = line.find(marker, idx)
        if pos < 0:
            return False
        before = line[pos - 1] if pos > 0 else " "
        after = line[pos + len(marker)] if pos + len(marker) < len(line) else " "
        if not (before.isalnum() or before == "_") and not (
            after.isalnum() or after == "_"
        ):
            return True
        idx = pos + len(marker)


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


def _render_prompt_with_budget(
    template: str,
    *,
    task_path: str,
    handoff_path: str,
    budget: ContextBudget | None = None,
) -> str:
    """Render the prompt, including bounded handoff recovery content.

    Fresh sessions do not include prior conversation transcripts. The
    optional ``budget`` is applied after the body is composed and is
    returned unchanged; the loop reads the budget event from
    :func:`sisyphusfy.context.apply_budget_to_prompt`.
    """
    body = _render_prompt(
        template,
        task_path=task_path,
        handoff_path=handoff_path,
    )
    if budget is not None and handoff_path:
        try:
            from pathlib import Path as _P

            path = _P(handoff_path)
            if path.exists():
                handoff_text = path.read_text()
                if (
                    budget.max_handoff_chars is not None
                    and len(handoff_text) > budget.max_handoff_chars
                ):
                    handoff_text = (
                        handoff_text[: budget.max_handoff_chars]
                        + "\n\n[handoff truncated by context budget]"
                    )
                body = f"{body}\n\nHandoff recovery:\n{handoff_text}"
        except OSError:
            pass
    return body


def _extract_blocker(result: object, markers: list[str] | None = None) -> str:
    """Pull the blocker text out of an agent run that emitted a blocked marker.

    Prefers the lines that actually contain a configured marker; falls back to
    the whole combined output so the operator still sees context. Kept short so
    it renders readably inside an interactive prompt. ``markers`` defaults to
    the global marker set; callers with configured markers pass them so the
    extraction agrees with the detection in :func:`_is_blocked`.
    """
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    combined = f"{stdout}\n{stderr}"
    active = [m for m in (markers if markers is not None else BLOCKED_MARKERS) if m and m.strip()]
    marker_lines = [
        line
        for line in combined.splitlines()
        if line.strip()
        for marker in active
        if _marker_token_present(line.strip(), marker) or line.strip() == marker
    ]
    if marker_lines:
        return "\n".join(marker_lines).strip()
    return combined.strip() or "(blocked marker detected in agent output)"


def _augment_prompt(original: str, blocker: str, answer: PromptAnswer) -> str:
    """Fold the operator's decision into a fresh agent prompt.

    The agent already exited; this is the only channel to tell the next, fresh
    invocation what was decided, so it can continue past the blocker.
    """
    quoted = "\n".join(f"> {line}" for line in blocker.splitlines() or [blocker])
    decision = (
        "You may proceed."
        if not answer.text
        else f"Decision from the operator: {answer.text}"
    )
    suffix = (
        "\n\nThe previous run stopped because of a blocked decision. "
        f"Blocker reported by the agent:\n{quoted}\n{decision}\n"
        "Continue the task with that decision applied."
    )
    return f"{original}{suffix}"


def _prepare_prompt(
    prompt: str,
    budget: ContextBudget | None,
    telemetry: ContextTelemetry,
) -> tuple[str, ContextEstimate, str | None]:
    """Apply the budget to one agent invocation and record telemetry.

    The single shared entry point for the iteration head and the
    interactive blocked-resolution re-run branch, so no invocation can
    bypass budget enforcement when a budget is configured. The budget
    event (``rejected``/``truncated``/``None``) is recorded on the
    telemetry and every invocation appends its estimate.
    """
    if budget is None:
        estimate = estimate_text(prompt)
        telemetry.record(estimate)
        return prompt, estimate, None
    final, event = apply_budget_to_prompt(prompt, budget)
    if event is not None:
        telemetry.budget_event = event
    estimate = estimate_text(final)
    telemetry.record(estimate)
    return final, estimate, event


def _maybe_compact_handoff(
    handoff_path: str | None,
    enabled: bool,
    telemetry: ContextTelemetry,
) -> object | None:
    """Compact the handoff file before rendering when opted in.

    Rewrites only the configured handoff file through
    :class:`HandoffCompactor` and records the before/after counts on
    the telemetry. Returns the compaction result or ``None``.
    """
    if not enabled or not handoff_path:
        return None
    try:
        result = HandoffCompactor().compact(handoff_path)
    except OSError:
        return None
    telemetry.compactions.append(result)
    return result


def _resolve_under(working_directory: str, path: str) -> str:
    """Resolve a configured path against the loop working directory."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    return str((Path(working_directory) / candidate).resolve())


def _ensure_inside_root(
    path: str,
    project_root: str,
    *,
    label: str,
    trust_outside_root: bool,
) -> str:
    """Validate that ``path`` resolves inside the project root.

    Raises :class:`ConfigurationError` when the resolved path escapes. An
    explicit ``trust_outside_root`` flag short-circuits the check for
    opt-in cases such as system-wide task lists.
    """
    if not path or trust_outside_root:
        return path
    try:
        resolved = Path(path).resolve()
    except OSError as exc:
        raise ConfigurationError(
            f"{label} path cannot be resolved: {path!r} ({exc})"
        ) from exc
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ConfigurationError(
            f"{label} path escapes project root: {path!r} "
            f"(resolves to {resolved}, root is {project_root})"
        ) from exc
    return str(resolved)


def _workspace_snapshot(
    working_directory: str,
    patterns: list[str],
) -> dict[str, str]:
    """Snapshot the content of files matching the configured patterns.

    A single source-of-truth is required so two iterations can be
    diffed: the snapshot is keyed by the relative path of every file
    that matched one of the glob patterns. Missing files are omitted.
    """
    if not patterns:
        return {}
    root = Path(working_directory)
    snap: dict[str, str] = {}
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            try:
                snap[rel] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return snap


def _has_workspace_change(
    before: dict[str, str], after: dict[str, str]
) -> bool:
    """Return True if any tracked workspace file changed."""
    return before != after


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
        build_for_model = getattr(adapter, "build_command_for_model", None)
        if model is not None and callable(build_for_model):
            cmd = build_for_model(working_directory, prompt, model)
        else:
            cmd = adapter.build_command(working_directory, prompt)
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
    telemetry = ContextTelemetry(budget=config.context_budget)
    result = _run_loop(config, evidence, telemetry)
    if result.verification is None and COMPONENT_VERIFY in evidence:
        result.verification = evidence[COMPONENT_VERIFY]
    if result.context_telemetry is None:
        result.context_telemetry = telemetry
    return result


def _run_loop(
    config: LoopConfig,
    evidence: dict[str, VerificationEvidence],
    telemetry: ContextTelemetry,
) -> LoopResult:
    working_directory = str(Path(config.working_directory).resolve())
    trust_outside = config.trust_paths_outside_root
    try:
        task_path = _ensure_inside_root(
            _resolve_under(working_directory, config.task_path) if config.task_path else "",
            working_directory,
            label="task_path",
            trust_outside_root=trust_outside,
        )
        handoff_path = (
            _ensure_inside_root(
                _resolve_under(working_directory, config.handoff_path),
                working_directory,
                label="handoff_path",
                trust_outside_root=trust_outside,
            )
            if config.handoff_path
            else None
        )
    except ConfigurationError as exc:
        raise ConfigurationError(str(exc)) from exc

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
                context_telemetry=telemetry,
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
                context_telemetry=telemetry,
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
            context_telemetry=telemetry,
        )

    def _blocked_stop(iteration: int, blocker: str) -> LoopResult:
        """Stop the iteration as blocked, carrying the operator-facing reason."""
        return LoopResult(
            stop_reason=LoopStopReason.BLOCKED,
            iterations=iteration,
            run_records=run_records,
            final_task_path=task_path,
            final_handoff_path=handoff_path,
            model_attempts=all_model_attempts,
            blocked_reason=blocker,
            context_telemetry=telemetry,
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
                context_telemetry=telemetry,
            )
        if vr.timed_out:
            return LoopResult(
                stop_reason=LoopStopReason.TIMEOUT,
                iterations=iteration,
                run_records=run_records,
                final_task_path=task_path,
                final_handoff_path=handoff_path,
                model_attempts=all_model_attempts,
                context_telemetry=telemetry,
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
                context_telemetry=telemetry,
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
            context_telemetry=telemetry,
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
            context_telemetry=telemetry,
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
            context_telemetry=telemetry,
        )
    if outcome is CompletionOutcome.COMPLETE:
        verification_failure = _run_verification(0)
        if verification_failure is not None:
            return verification_failure
        return _complete(0)

    completed_iteration = 0
    try:
        prev_state = _snapshot(task_path, handoff_path)
        prev_workspace = _workspace_snapshot(
            working_directory, config.workspace_evidence
        )

        for i in range(1, config.max_iterations + 1):
            completed_iteration = i
            _maybe_compact_handoff(handoff_path, config.compact_handoff, telemetry)
            raw = _render_prompt_with_budget(
                config.prompt_template,
                task_path=task_path,
                handoff_path=handoff_path or "",
                budget=config.context_budget,
            )
            prompt, estimate, event = _prepare_prompt(
                raw, config.context_budget, telemetry
            )
            if event == "rejected":
                return LoopResult(
                    stop_reason=LoopStopReason.CONTEXT_BUDGET_EXCEEDED,
                    iterations=i - 1,
                    run_records=run_records,
                    final_task_path=task_path,
                    final_handoff_path=handoff_path,
                    model_attempts=all_model_attempts,
                    context_telemetry=telemetry,
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
                    if exc.last_result is None:
                        # No attempt ran: every model was skipped as
                        # unsupported. Stop with the skip list as the audit
                        # trail instead of agent evidence there is none.
                        skipped = getattr(exc, "skipped", []) or list(
                            config.model_chain
                        )
                        return LoopResult(
                            stop_reason=LoopStopReason.MODELS_EXHAUSTED,
                            iterations=i,
                            run_records=run_records,
                            final_task_path=task_path,
                            final_handoff_path=handoff_path,
                            model_attempts=exc.attempts,
                            adapter_error=(
                                "no supported model in chain: "
                                f"{', '.join(skipped)}"
                            ),
                            context_telemetry=telemetry,
                        )
                    return _agent_stop(
                        LoopStopReason.MODELS_EXHAUSTED,
                        i,
                        exc.last_result,
                        model_attempts=exc.attempts,
                    )
            else:
                result = _run_with_model(model=adapter.model if adapter else None)

            rec = RunRecord(
                iteration=i,
                result=result,
                prompt=prompt,
                context_estimate=estimate,
            )
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
                blocker = _extract_blocker(result, config.blocked_markers)
                if config.interactive and config.prompt_user is not None:
                    prompt_user = config.prompt_user
                    resolved = False
                    for _ in range(config.max_interactive_prompts):
                        answer = prompt_user(blocker)
                        if answer.denied:
                            return _blocked_stop(i, blocker)
                        augmented = _augment_prompt(prompt, blocker, answer)
                        rerun_prompt, rerun_estimate, rerun_event = _prepare_prompt(
                            augmented, config.context_budget, telemetry
                        )
                        if rerun_event == "rejected":
                            return LoopResult(
                                stop_reason=LoopStopReason.CONTEXT_BUDGET_EXCEEDED,
                                iterations=i,
                                run_records=run_records,
                                final_task_path=task_path,
                                final_handoff_path=handoff_path,
                                model_attempts=all_model_attempts,
                                context_telemetry=telemetry,
                            )
                        result = _run_with_model(p=rerun_prompt)
                        run_records.append(
                            RunRecord(
                                iteration=i,
                                result=result,
                                prompt=rerun_prompt,
                                context_estimate=rerun_estimate,
                            )
                        )
                        if len(run_records) > config.max_run_records:
                            run_records = run_records[-config.max_run_records:]
                        # An interrupt/timeout during the re-run still stops.
                        if getattr(result, "interrupted", False):
                            return _agent_stop(LoopStopReason.INTERRUPTED, i, result)
                        if result.timed_out:
                            return _agent_stop(LoopStopReason.TIMEOUT, i, result)
                        if not _is_blocked(result, config.blocked_markers):
                            resolved = True
                            break
                        # Still blocked: refresh the blocker text and re-prompt.
                        blocker = _extract_blocker(result, config.blocked_markers)
                    if resolved:
                        # Continues past the blocker into verification/completion.
                        pass
                    else:
                        return _blocked_stop(i, blocker)
                else:
                    return _blocked_stop(i, blocker)

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
                    context_telemetry=telemetry,
                )
            if outcome is CompletionOutcome.COMPLETE:
                return _complete(i)

            curr_state = _snapshot(task_path, handoff_path)
            if not _changed(prev_state, curr_state):
                if config.workspace_evidence:
                    curr_workspace = _workspace_snapshot(
                        working_directory, config.workspace_evidence
                    )
                    if not _has_workspace_change(prev_workspace, curr_workspace):
                        return LoopResult(
                            stop_reason=LoopStopReason.UNCHANGED_STATE,
                            iterations=i,
                            run_records=run_records,
                            final_task_path=task_path,
                            final_handoff_path=handoff_path,
                            model_attempts=all_model_attempts,
                            context_telemetry=telemetry,
                        )
                    prev_workspace = curr_workspace
                else:
                    return LoopResult(
                        stop_reason=LoopStopReason.UNCHANGED_STATE,
                        iterations=i,
                        run_records=run_records,
                        final_task_path=task_path,
                        final_handoff_path=handoff_path,
                        model_attempts=all_model_attempts,
                        context_telemetry=telemetry,
                    )
            else:
                prev_state = curr_state

    except KeyboardInterrupt:
        return LoopResult(
            stop_reason=LoopStopReason.INTERRUPTED,
            iterations=completed_iteration,
            run_records=run_records,
            final_task_path=task_path,
            final_handoff_path=handoff_path,
            model_attempts=all_model_attempts,
            context_telemetry=telemetry,
        )

    return LoopResult(
        stop_reason=LoopStopReason.MAX_ITERATIONS,
        iterations=config.max_iterations,
        run_records=run_records,
        final_task_path=task_path,
        final_handoff_path=handoff_path,
        model_attempts=all_model_attempts,
        context_telemetry=telemetry,
    )


def _is_provider_side_error(error: AgentError | None) -> bool:
    """Return True for a generic server/provider error, not a specific agent error.

    A specific, actionable error (a clear ``RateLimitError``, a missing file,
    etc.) must stay prominent; only a generic "server error" envelope is
    annotated with an agent-CLI diagnostic hint.
    """
    if error is None:
        return False
    if error.name and error.name.lower() in _GENERIC_SERVER_ERRORS:
        return True
    message = (error.message or "").lower()
    return any(token in message for token in _GENERIC_SERVER_ERROR_TOKENS)


_GENERIC_SERVER_ERRORS = {"unknownerror", "servererror", "internalerror"}
_GENERIC_SERVER_ERROR_TOKENS = (
    "server error",
    "server logs",
    "check server logs",
    "unexpected server",
)


def _adapter_diagnostic_hint(adapter: AgentAdapter) -> str | None:
    """Return the adapter's diagnostic hint, tolerating adapters without one."""
    hint = getattr(adapter, "diagnostic_hint", None)
    if hint is None:
        return None
    try:
        return hint()
    except Exception:  # noqa: BLE001 - a third-party adapter must not stop the loop
        return None


def _parse_agent_error(adapter: AgentAdapter, result: object) -> AgentError | None:
    """Ask an adapter for the structured agent error, if it exposes one.

    Third-party adapters written against the earlier protocol have no
    `parse_error`, and an adapter that raises must not take the supervisor
    down. Either case degrades to "no structured error" while the stop reason
    still reflects the non-zero exit status. When the recovered error is a
    generic provider/server error, a diagnostic hint from the adapter is
    attached so the user is pointed at their agent CLI instead of a dead end.
    """
    parse = getattr(adapter, "parse_error", None)
    if parse is None:
        return None
    combined = (
        f"{getattr(result, 'stdout', '') or ''}\n"
        f"{getattr(result, 'stderr', '') or ''}"
    )
    try:
        error = parse(combined)
    except Exception:  # noqa: BLE001 - a third-party parser must not stop the loop
        return None
    if error is not None and _is_provider_side_error(error):
        hint = _adapter_diagnostic_hint(adapter)
        if hint:
            error.hint = hint
    return error


def _make_generic(command: list[str]) -> AgentAdapter:
    from sisyphusfy.adapters import GenericCommandAdapter
    return GenericCommandAdapter(command=command)
