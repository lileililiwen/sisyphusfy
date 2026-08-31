"""High-level human-friendly commands: run, resume, status, doctor."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from sisyphusfy.config import (
    SisyphusConfig,
    apply_cli_overrides,
    discover_handoff_path,
    discover_openspec_change,
    discover_task_path,
    find_verification_command,
    init_project_config,
    load_config,
)


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

    verification_command = config.verification_command or None
    if not verification_command:
        verification_command = find_verification_command(project_dir)

    if dry_run:
        return _dry_run_output(
            config=config,
            project_dir=project_dir,
            task_path=task_path,
            handoff_path=handoff_path,
            workflow_type=workflow_type,
            openspec_dir=openspec_dir,
            verification_command=verification_command,
            json_output=json_output,
        )

    return _execute_loop(
        config=config,
        project_dir=project_dir,
        task_path=task_path,
        handoff_path=handoff_path,
        workflow_type=workflow_type,
        openspec_dir=openspec_dir,
        verification_command=verification_command,
        json_output=json_output,
    )


def cmd_resume(
    project_dir: str = ".",
    json_output: bool = False,
    dry_run: bool = False,
    max_iterations: int | None = None,
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

    verification_command = config.verification_command or None
    if not verification_command:
        verification_command = find_verification_command(project_dir)

    if dry_run:
        return _dry_run_output(
            config=config,
            project_dir=project_dir,
            task_path=task_path,
            handoff_path=handoff_path,
            workflow_type=workflow_type,
            openspec_dir=openspec_dir,
            verification_command=verification_command,
            json_output=json_output,
        )

    return _execute_loop(
        config=config,
        project_dir=project_dir,
        task_path=task_path,
        handoff_path=handoff_path,
        workflow_type=workflow_type,
        openspec_dir=openspec_dir,
        verification_command=verification_command,
        json_output=json_output,
    )


def cmd_status(project_dir: str = ".", json_output: bool = False) -> int:
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

    if json_output:
        print(json.dumps(status_data, indent=2))
    else:
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

    return 0


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

    if config.verification_command:
        cmd_name = config.verification_command[0]
        if not shutil.which(cmd_name):
            issues.append(f"verification command not found: {cmd_name}")
    else:
        auto_verify = find_verification_command(project_dir)
        if auto_verify is None:
            warnings.append("no verification command configured or auto-detected")

    project_path = Path(project_dir).resolve()
    config_file = project_path / ".sisyphusfy.toml"
    if not config_file.exists():
        warnings.append("no .sisyphusfy.toml; using defaults (run 'sisyphusfy init' to create)")

    if json_output:
        print(json.dumps({"issues": issues, "warnings": warnings, "ok": len(issues) == 0}))
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
        print("status: ok" if not issues else "status: issues found")

    return 0 if not issues else 1


def _dry_run_output(
    config: SisyphusConfig,
    project_dir: str,
    task_path: str,
    handoff_path: str | None,
    workflow_type: str,
    openspec_dir: str | None,
    verification_command: list[str] | None,
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
        "verification_command": verification_command,
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
        if verification_command:
            print(f"  verify:      {' '.join(verification_command)}")
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
    verification_command: list[str] | None,
    json_output: bool,
) -> int:
    from sisyphusfy.adapters import AdapterConfig
    from sisyphusfy.hooks import HookConfig, HookType
    from sisyphusfy.loop import LoopConfig, MarkdownCheckboxCompletion, run_loop
    from sisyphusfy.workflows import WorkflowConfig

    project_path = str(Path(project_dir).resolve())

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
        verification_command=verification_command,
        verification_timeout=config.verification_timeout,
        agent_timeout=config.agent_timeout,
        max_iterations=config.max_iterations,
        completion_strategy=completion_strategy,
        adapter_config=adapter_config,
        model_chain=config.model_chain,
        completion_hooks=completion_hooks,
        dry_run=False,
        workflow_config=workflow_config,
    )

    result = run_loop(loop_config)

    if json_output:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        _print_human_result(result, config)

    return 0 if result.stop_reason.value == "complete" else 1


def _print_human_result(result, config: SisyphusConfig) -> None:
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

    print()

    if reason == "complete":
        print("done. all tasks complete.")
    elif reason == "max_iterations":
        print(f"stopped after {result.iterations} iterations (max: {config.max_iterations})")
        print("resume with: sisyphusfy resume")
    elif reason == "blocked":
        print("blocked. agent requested permission or encountered an ambiguity.")
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
        print("verification failed after iteration.")
        print("resume with: sisyphusfy resume")
    elif reason == "timeout":
        print("agent timed out.")
        print("resume with: sisyphusfy resume")
    else:
        print(f"stopped: {reason}")
