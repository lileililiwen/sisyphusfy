"""High-level human-friendly commands: run, resume, status, doctor."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from sisyphusfy.config import (
    SisyphusConfig,
    VerificationResolution,
    VerificationSource,
    apply_cli_overrides,
    discover_handoff_path,
    discover_openspec_change,
    discover_task_path,
    init_project_config,
    load_config,
    resolve_verification,
)
from sisyphusfy.diagnostics import read_verification_log
from sisyphusfy.git import DiffMode, GitInspection
from sisyphusfy.git import inspect as git_inspect
from sisyphusfy.progress import StreamProgress, format_duration
from sisyphusfy.result import format_command

# How many trailing output lines a timeout report shows.
TIMEOUT_TAIL_LINES = 5

# How many characters of each trailing line a timeout report shows.
TIMEOUT_TAIL_CHARS = 200

# Default bound on the diff payload for the human CLI. The unified diff is
# truncated to this many bytes; the truncation flag travels with both the
# human and the structured result.
DEFAULT_DIFF_MAX_BYTES = 50_000

# How many status entries a concise status --diff print shows before
# collapsing the rest under an "+N more" line.
STATUS_DIFF_PREVIEW_ENTRIES = 20


def cmd_init(project_dir: str = ".", force: bool = False, json_output: bool = False) -> int:
    try:
        config_path = init_project_config(project_dir, force=force)
    except FileExistsError as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "created": False}))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1

    if json_output:
        print(json.dumps({"config_path": str(config_path), "created": True}))
    else:
        print(f"created {config_path}")
        print("configure with CLI flags, this file, or ~/.config/sisyphusfy/config.toml")
    return 0


def cmd_run(
    project_dir: str = ".",
    change: str | None = None,
    json_output: bool = False,
    dry_run: bool = False,
    archive: bool = False,
    commit: bool = False,
    max_iterations: int | None = None,
    verbose: bool = False,
    interactive: bool | None = None,
    **cli_overrides,
) -> int:
    config = load_config(project_dir)
    if max_iterations is not None:
        config.max_iterations = max_iterations
    config = apply_cli_overrides(config, **cli_overrides)

    if archive:
        config.archive_enabled = True
    if commit:
        config.commit_enabled = True

    openspec_dir = discover_openspec_change(project_dir, change)
    task_path = None
    workflow_type = config.workflow_type

    if openspec_dir:
        task_path = str(Path(openspec_dir) / "tasks.md")
        workflow_type = "openspec"
    elif change:
        task_path = discover_task_path(project_dir, change)
        if task_path is None:
            msg = f"change not found: {change}"
            if json_output:
                print(json.dumps({"error": msg}))
            else:
                print(f"error: {msg}", file=sys.stderr)
            return 1
    else:
        task_path = discover_task_path(project_dir)

    if task_path is None:
        msg = "no task file found; create tasks.md or specify a change name"
        if json_output:
            print(json.dumps({"error": msg}))
        else:
            print(f"error: {msg}", file=sys.stderr)
        return 1

    handoff_path = discover_handoff_path(project_dir, config)

    verification = resolve_verification(config.verification_command, project_dir)

    if dry_run:
        return _dry_run_output(
            config=config,
            project_dir=project_dir,
            task_path=task_path,
            handoff_path=handoff_path,
            workflow_type=workflow_type,
            openspec_dir=openspec_dir,
            verification=verification,
            json_output=json_output,
        )

    return _execute_loop(
        config=config,
        project_dir=project_dir,
        task_path=task_path,
        handoff_path=handoff_path,
        workflow_type=workflow_type,
        openspec_dir=openspec_dir,
        verification=verification,
        json_output=json_output,
        verbose=verbose,
        interactive=interactive,
    )


def cmd_resume(
    project_dir: str = ".",
    json_output: bool = False,
    dry_run: bool = False,
    max_iterations: int | None = None,
    verbose: bool = False,
    interactive: bool | None = None,
    **cli_overrides,
) -> int:
    config = load_config(project_dir)
    if max_iterations is not None:
        config.max_iterations = max_iterations
    config = apply_cli_overrides(config, **cli_overrides)

    task_path = discover_task_path(project_dir)
    handoff_path = discover_handoff_path(project_dir, config)

    if task_path is None:
        msg = "no task file found to resume"
        if json_output:
            print(json.dumps({"error": msg}))
        else:
            print(f"error: {msg}", file=sys.stderr)
        return 1

    workflow_type = config.workflow_type
    openspec_dir = discover_openspec_change(project_dir)
    if openspec_dir:
        workflow_type = "openspec"

    verification = resolve_verification(config.verification_command, project_dir)

    if dry_run:
        return _dry_run_output(
            config=config,
            project_dir=project_dir,
            task_path=task_path,
            handoff_path=handoff_path,
            workflow_type=workflow_type,
            openspec_dir=openspec_dir,
            verification=verification,
            json_output=json_output,
        )

    return _execute_loop(
        config=config,
        project_dir=project_dir,
        task_path=task_path,
        handoff_path=handoff_path,
        workflow_type=workflow_type,
        openspec_dir=openspec_dir,
        verification=verification,
        json_output=json_output,
        verbose=verbose,
        interactive=interactive,
    )


def cmd_status(
    project_dir: str = ".",
    json_output: bool = False,
    show_diff: bool = False,
) -> int:
    config = load_config(project_dir)
    task_path = discover_task_path(project_dir)
    handoff_path = discover_handoff_path(project_dir, config)
    openspec_dir = discover_openspec_change(project_dir)

    checked = 0
    unchecked = 0
    task_file_exists = task_path is not None and Path(task_path).exists()
    handoff_file_exists = handoff_path is not None and Path(handoff_path).exists()

    if task_file_exists:
        for line in Path(task_path).read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith(("- [x]", "- [X]")):
                checked += 1
            elif stripped.startswith("- [ ]"):
                unchecked += 1

    state = "idle"
    if unchecked > 0:
        state = "in_progress"
    elif checked > 0 and unchecked == 0:
        state = "complete"

    status_data = {
        "config_adapter": config.adapter,
        "config_model_chain": config.model_chain,
        "config_workflow_type": config.workflow_type,
        "task_path": task_path,
        "handoff_path": handoff_path,
        "task_file_exists": task_file_exists,
        "handoff_file_exists": handoff_file_exists,
        "openspec_change": openspec_dir,
        "tasks_checked": checked,
        "tasks_unchecked": unchecked,
        "state": state,
    }

    if show_diff:
        status_data["git"] = _read_only_git_snapshot(project_dir).to_dict()

    if json_output:
        print(json.dumps(status_data, indent=2))
        return 0

    print(f"adapter:    {config.adapter}")
    print(f"model_chain: {', '.join(config.model_chain) if config.model_chain else '(none)'}")
    print(f"workflow:   {config.workflow_type}")
    print()
    if task_path:
        print(f"task:       {task_path}")
    else:
        print("task:       (none)")
    if handoff_path:
        print(f"handoff:    {handoff_path}")
    else:
        print("handoff:    (none)")
    if openspec_dir:
        print(f"openspec:   {openspec_dir}")
    print()
    if task_file_exists:
        print(f"tasks:      {checked} checked, {unchecked} unchecked")
        print(f"state:      {state}")
    else:
        print("tasks:      (no task file)")

    if show_diff:
        _print_git_snapshot(_read_only_git_snapshot(project_dir))

    return 0


def cmd_diff(
    project_dir: str = ".",
    staged: bool = False,
    stat: bool = False,
    json_output: bool = False,
    max_bytes: int = DEFAULT_DIFF_MAX_BYTES,
) -> int:
    """Show a read-only Git status and diff for the selected project.

    The command is read-only. It runs no `git add`, `git commit`, or
    `git push` and never modifies the working tree. Missing Git and
    non-repository directories are reported as structured unavailable
    results, not exceptions.
    """
    mode = DiffMode.STAGED if staged else DiffMode.UNSTAGED
    snapshot = git_inspect(
        project_dir,
        mode=mode,
        stat_only=stat,
        max_bytes=max_bytes,
    )

    if json_output:
        print(json.dumps({"git": snapshot.to_dict()}, indent=2))
        return 0

    _print_git_snapshot(snapshot, stat_only=stat, mode=mode)
    return 0


def _read_only_git_snapshot(project_dir: str) -> GitInspection:
    """Read a snapshot of the working tree for the human CLI.

    The command is `git diff` only and never touches the index. This is
    a convenience wrapper around the read-only Git adapter.
    """
    return git_inspect(project_dir, mode=DiffMode.UNSTAGED)


def _print_git_snapshot(
    snapshot: GitInspection,
    *,
    stat_only: bool = False,
    mode: DiffMode = DiffMode.UNSTAGED,
) -> None:
    """Render a GitInspection to the human CLI stream.

    A unavailable state prints one labelled line and exits. An available
    state prints the branch, a count of changed files, the first few
    status entries, and (unless `stat_only` is set) a bounded unified
    diff. The diff is always capped by the snapshot's own truncation
    flag -- the human CLI never prints the full untruncated payload
    unless `inspect` decided the diff fit.
    """
    print()
    print("git:")
    if not snapshot.available:
        reason = snapshot.reason or "unavailable"
        print(f"  inspection: {reason}")
        return

    print(f"  branch:   {snapshot.branch or '(detached)'}")
    print(f"  changed:  {snapshot.changed_files} file(s)")
    if snapshot.status_paths:
        preview = snapshot.status_paths[:STATUS_DIFF_PREVIEW_ENTRIES]
        for entry, path in zip(snapshot.status_entries[:STATUS_DIFF_PREVIEW_ENTRIES], preview):
            print(f"    {entry.status} {path}")
        extra = len(snapshot.status_paths) - len(preview)
        if extra > 0:
            print(f"    +{extra} more")
    else:
        print("    (clean)")

    if stat_only:
        if snapshot.stat_text:
            print()
            print(snapshot.stat_text)
        return

    if mode is DiffMode.STAGED:
        label = "staged diff"
    else:
        label = "unstaged diff"
    if not snapshot.diff_text:
        print(f"  {label}: (empty)")
        return
    print()
    print(f"  {label}:")
    for line in snapshot.diff_text.splitlines():
        print(f"    {line}")
    if snapshot.truncated:
        print("    ... (diff truncated)")


def cmd_doctor(project_dir: str = ".", json_output: bool = False) -> int:
    config = load_config(project_dir)
    issues: list[str] = []
    warnings: list[str] = []

    adapter_bin = config.adapter
    if adapter_bin == "opencode":
        if not shutil.which("opencode"):
            issues.append("agent 'opencode' not found on PATH")
    elif adapter_bin == "codebuddy":
        if not shutil.which("codebuddy"):
            issues.append("agent 'codebuddy' not found on PATH")
    else:
        if not shutil.which(adapter_bin):
            issues.append(f"adapter '{adapter_bin}' not found on PATH")

    task_path = discover_task_path(project_dir)
    if task_path is None:
        warnings.append("no task file found (tasks.md, TASKS.md, task.md, TASK.md)")
    elif not Path(task_path).exists():
        issues.append(f"task path configured but missing: {task_path}")

    handoff_path = discover_handoff_path(project_dir, config)
    if handoff_path is None:
        warnings.append(f"handoff file not found (expected {config.handoff_path})")

    openspec_dir = discover_openspec_change(project_dir)
    openspec_cli = shutil.which("openspec")
    if openspec_dir and not openspec_cli:
        warnings.append("openspec change detected but 'openspec' CLI not found")

    verification = resolve_verification(config.verification_command, project_dir)
    if verification.source is VerificationSource.CONFIGURED:
        cmd_name = verification.command[0]
        if not shutil.which(cmd_name):
            issues.append(f"verification command not found: {cmd_name}")
    elif verification.source is VerificationSource.UNAVAILABLE:
        detail = f" ({verification.detail})" if verification.detail else ""
        warnings.append(
            "no verification command configured or detected"
            f"{detail}; set verification_command for a release gate"
        )

    project_path = Path(project_dir).resolve()
    config_file = project_path / ".sisyphusfy.toml"
    if not config_file.exists():
        warnings.append("no .sisyphusfy.toml; using defaults (run 'sisyphusfy init' to create)")

    if json_output:
        print(json.dumps({
            "issues": issues,
            "warnings": warnings,
            "ok": len(issues) == 0,
            "verification": verification.to_dict(),
        }))
    else:
        if issues:
            print("issues:")
            for issue in issues:
                print(f"  - {issue}")
        if warnings:
            print("warnings:")
            for w in warnings:
                print(f"  - {w}")
        if not issues and not warnings:
            print("no issues found")
        print()
        print(f"verification: {_describe_verification(verification)}")
        print("status: ok" if not issues else "status: issues found")

    return 0 if not issues else 1


def _describe_verification(verification: VerificationResolution) -> str:
    """Render the resolved verifier and how it was chosen."""
    if verification.source is VerificationSource.CONFIGURED:
        return f"configured: {format_command(verification.command)}"
    if verification.source is VerificationSource.DISCOVERED:
        return f"discovered ({verification.detector}): {format_command(verification.command)}"
    detail = f" ({verification.detail})" if verification.detail else ""
    return f"none found{detail}; set verification_command"


def _dry_run_output(
    config: SisyphusConfig,
    project_dir: str,
    task_path: str,
    handoff_path: str | None,
    workflow_type: str,
    openspec_dir: str | None,
    verification: VerificationResolution,
    json_output: bool,
) -> int:
    data = {
        "dry_run": True,
        "project_dir": str(Path(project_dir).resolve()),
        "adapter": config.adapter,
        "model_chain": config.model_chain,
        "task_path": task_path,
        "handoff_path": handoff_path,
        "workflow_type": workflow_type,
        "openspec_dir": openspec_dir,
        "verification_command": verification.command or None,
        "verification": verification.to_dict(),
        "max_iterations": config.max_iterations,
        "agent_timeout": config.agent_timeout,
        "archive_enabled": config.archive_enabled,
        "commit_enabled": config.commit_enabled,
        "commit_allowed_files": config.commit_allowed_files,
    }

    if json_output:
        print(json.dumps(data, indent=2))
    else:
        print("dry-run: planned loop configuration")
        print(f"  project:    {Path(project_dir).resolve()!s}")
        print(f"  adapter:     {config.adapter}")
        if config.model_chain:
            print(f"  models:      {' -> '.join(config.model_chain)}")
        print(f"  task:        {task_path}")
        if handoff_path:
            print(f"  handoff:     {handoff_path}")
        print(f"  workflow:    {workflow_type}")
        if openspec_dir:
            print(f"  openspec:    {openspec_dir}")
        print(f"  verify:      {_describe_verification(verification)}")
        print(f"  iterations:  {config.max_iterations}")
        print(f"  timeout:     {config.agent_timeout}s")
        print(f"  archive:     {'enabled' if config.archive_enabled else 'disabled'}")
        print(f"  commit:      {'enabled' if config.commit_enabled else 'disabled'}")

    return 0


def _execute_loop(
    config: SisyphusConfig,
    project_dir: str,
    task_path: str,
    handoff_path: str | None,
    workflow_type: str,
    openspec_dir: str | None,
    verification: VerificationResolution,
    json_output: bool,
    verbose: bool = False,
    interactive: bool | None = None,
) -> int:
    from sisyphusfy.adapters import AdapterConfig
    from sisyphusfy.hooks import HookConfig, HookType
    from sisyphusfy.loop import LoopConfig, MarkdownCheckboxCompletion, run_loop
    from sisyphusfy.workflows import WorkflowConfig

    project_path = str(Path(project_dir).resolve())

    # Resolve interactive mode: explicit flag wins; otherwise auto-detect a
    # terminal; never interactive under JSON output (it must not block for input).
    effective_interactive = bool(interactive) if interactive is not None else sys.stdin.isatty()
    if json_output:
        effective_interactive = False

    adapter_config = AdapterConfig(
        name=config.adapter,
        model=config.model_chain[0] if config.model_chain else None,
    )

    completion_strategy = MarkdownCheckboxCompletion()

    workflow_config = None
    if workflow_type == "openspec" and openspec_dir:
        workflow_config = WorkflowConfig(
            adapter_type="openspec",
            task_path=task_path,
            change_dir=openspec_dir,
            validation_command=config.verification_command or [],
            timeout=config.verification_timeout,
            working_directory=project_path,
        )

    completion_hooks = []
    if config.archive_enabled:
        archive_cmd = ["openspec", "archive", "--yes"]
        if openspec_dir:
            change_name = Path(openspec_dir).name
            archive_cmd = ["openspec", "archive", change_name, "--yes"]
        completion_hooks.append(
            HookConfig(
                hook_type=HookType.ARCHIVE,
                command=archive_cmd,
                working_directory=project_path,
                enabled=True,
            )
        )
    if config.commit_enabled:
        completion_hooks.append(
            HookConfig(
                hook_type=HookType.COMMIT,
                command=["git", "commit", "-m", "sisyphusfy: completed iteration"],
                working_directory=project_path,
                allowed_files=config.commit_allowed_files,
                enabled=True,
            )
        )

    loop_config = LoopConfig(
        agent_command=[config.adapter],
        working_directory=project_path,
        task_path=task_path,
        handoff_path=handoff_path,
        verification_command=verification.command or None,
        verification_timeout=config.verification_timeout,
        verification_source=verification.source.value,
        verification_detector=verification.detector,
        agent_timeout=config.agent_timeout,
        max_iterations=config.max_iterations,
        completion_strategy=completion_strategy,
        adapter_config=adapter_config,
        model_chain=config.model_chain,
        completion_hooks=completion_hooks,
        dry_run=False,
        workflow_config=workflow_config,
        interactive=effective_interactive,
        # Progress is streamed for human output only; JSON stays machine-readable.
        progress=None if json_output else StreamProgress(stream=sys.stderr),
    )

    result = run_loop(loop_config)

    if json_output:
        data = result.to_dict()
        if data.get("verification") is None:
            data["verification"] = {
                "command": [],
                "source": verification.source.value,
                "detector": verification.detector,
                "status": "skipped",
                "log_path": None,
            }
        print(json.dumps(data, indent=2))
    else:
        _print_human_result(result, config, verification)
        if verbose:
            print_verification_log(result)

    return 0 if result.stop_reason.value == "complete" else 1


def print_verification_log(result) -> None:
    """Print the saved diagnostics when the user asks for them.

    A run that stopped on the agent keeps agent diagnostics and no verification
    evidence; reporting "none captured" there would contradict the inspect
    instruction printed beside the agent log path.
    """
    evidence = result.verification or getattr(result, "agent_evidence", None)
    label = "verification" if result.verification is not None else "agent"
    if evidence is None or not evidence.log_path:
        print("no verification diagnostics were captured")
        return
    text = read_verification_log(evidence.log_path)
    if text is None:
        print(f"{label} log is missing: {evidence.log_path}")
        return
    print(f"{label} diagnostics: {evidence.log_path}")
    print(text, end="" if text.endswith("\n") else "\n")


def _print_human_result(
    result,
    config: SisyphusConfig,
    verification: VerificationResolution | None = None,
) -> None:
    reason = result.stop_reason.value

    if result.iterations > 0:
        last = result.run_records[-1] if result.run_records else None
        if last:
            last_result = last.result
            status = "OK" if getattr(last_result, "exit_status", None) == 0 else f"exit {getattr(last_result, 'exit_status', '?')}"
            print(f"iteration {result.iterations}: [{status}]")

    if result.model_attempts:
        print(f"models tried: {', '.join(result.model_attempts)}")

    if result.adapter_error:
        print(f"adapter error: {result.adapter_error}")

    if result.completion_pipeline_result:
        for hook in result.completion_pipeline_result.hooks:
            print(f"hook {hook.hook_type.value}: {hook.status.value}")

    if verification is not None and verification.source is VerificationSource.UNAVAILABLE:
        print("verification: none found; no verifier ran (set verification_command)")

    print()

    if reason == "complete":
        print("done. all tasks complete.")
    elif reason == "max_iterations":
        print(f"stopped after {result.iterations} iterations (max: {config.max_iterations})")
        print("resume with: sisyphusfy resume")
    elif reason == "blocked":
        print("blocked. agent requested permission or encountered an ambiguity.")
        if getattr(result, "blocked_reason", None):
            for line in result.blocked_reason.splitlines() or [result.blocked_reason]:
                print(f"  blocker: {line}")
        if result.final_task_path:
            print(f"task state preserved at: {result.final_task_path}")
        if result.final_handoff_path:
            print(f"handoff at: {result.final_handoff_path}")
        print("resume with: sisyphusfy resume")
    elif reason == "unchanged_state":
        print("stopped: task state unchanged after iteration.")
        print("resume with: sisyphusfy resume")
    elif reason == "models_exhausted":
        print("all configured models exhausted.")
        if result.model_attempts:
            print(f"tried: {', '.join(result.model_attempts)}")
    elif reason == "verification_failed":
        _print_verifier_status(result, "failed")
        print("resume with: sisyphusfy resume")
    elif reason == "agent_failed":
        _print_agent_failure(result)
        print("stopped: agent_failed")
        print("resume with: sisyphusfy resume")
    elif reason == "timeout":
        _print_timeout(result, config)
        print("resume with: sisyphusfy resume")
    elif reason == "interrupted":
        print("interrupted. no durable state was changed by the supervisor.")
        if result.final_task_path:
            print(f"task state: {result.final_task_path}")
        if result.final_handoff_path:
            print(f"handoff: {result.final_handoff_path}")
        print("resume with: sisyphusfy resume")
    else:
        print(f"stopped: {reason}")


def _print_timeout(result, config: SisyphusConfig) -> None:
    """Report the timed-out component, its limit, its output, and its log."""
    verification = result.verification
    if verification is not None and verification.timed_out:
        _print_timeout_detail("verify", verification, config.verification_timeout)
    elif result.agent_evidence is not None:
        _print_timeout_detail("agent", result.agent_evidence, config.agent_timeout)
    else:
        print(f"agent timed out after {format_duration(config.agent_timeout)}.")


def _print_timeout_detail(component: str, evidence, limit: float) -> None:
    print(f"{component} timed out after {format_duration(limit)}: {format_command(evidence.command)}")
    for line in _timeout_tail(evidence):
        print(f"  {line}")
    if evidence.log_path:
        print(f"  diagnostics: {evidence.log_path}")
        print("  inspect with: sisyphusfy resume --verbose")
    else:
        print("  diagnostics: not written")


def _timeout_tail(evidence) -> list[str]:
    """Return the last lines of captured output, bounded for display."""
    stream = f"{evidence.stdout or ''}{evidence.stderr or ''}"
    lines = [line.strip() for line in stream.splitlines() if line.strip()]
    return [line[:TIMEOUT_TAIL_CHARS] for line in lines[-TIMEOUT_TAIL_LINES:]]


def _print_agent_failure(result) -> None:
    """Report the failed agent, any recovered error, and its diagnostics."""
    evidence = result.agent_evidence
    if evidence is None:
        print("[agent] failed.")
        return

    command = Path(evidence.command[0]).name if evidence.command else "agent"
    exit_status = "?" if evidence.exit_status is None else str(evidence.exit_status)
    print(f"[agent] failed: {command} exited with code {exit_status}")

    error = result.agent_error
    detail = error.message or error.name if error is not None else None
    if detail:
        print(f"[agent] error: {detail}")
    if error is not None and error.reference:
        print(f"[agent] reference: {error.reference}")
    if error is not None and error.hint:
        print("[agent] this is an agent-CLI/provider error, not a sisyphusfy failure.")
        print(f"[agent] diagnose: {error.hint}")

    if evidence.log_path:
        print(f"[agent] diagnostics: {evidence.log_path}")
        print("[agent] inspect with: sisyphusfy resume --verbose")
    else:
        print("[agent] diagnostics: not written")


def _print_verifier_status(result, outcome: str) -> None:
    """Report the verifier, its status, and where its full output was saved."""
    evidence = result.verification
    if evidence is None:
        print(f"verification {outcome}.")
        return
    status = "timed out" if evidence.timed_out else f"exit {evidence.exit_status}"
    print(f"verification {outcome}: {format_command(evidence.command)} ({status})")
    if evidence.log_path:
        print(f"  diagnostics: {evidence.log_path}")
        print("  inspect with: sisyphusfy resume --verbose")
    else:
        print("  diagnostics: not written")
