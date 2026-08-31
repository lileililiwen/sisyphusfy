from __future__ import annotations

import argparse
import json
import sys

from sisyphusfy.progress import StreamProgress
from sisyphusfy.runner import run_agent

HIGH_LEVEL_SUBCOMMANDS = {"init", "run", "resume", "status", "doctor"}

# Conventional exit status for a command stopped by an interrupt.
INTERRUPTED_EXIT_STATUS = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sisyphusfy",
        description="Run one configured agent invocation",
    )
    parser.add_argument(
        "--working-directory", "-d", default=".", help="Working directory for the agent"
    )
    parser.add_argument(
        "--prompt", "-p", default=None, help="Prompt to send to the agent via stdin"
    )
    parser.add_argument(
        "--timeout", "-t", type=float, default=60.0, help="Timeout in seconds"
    )
    parser.add_argument(
        "--env",
        "-e",
        action="append",
        default=None,
        metavar="KEY=VALUE",
        help="Environment variable (repeatable)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the command without executing"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true", help="Output structured JSON"
    )
    return parser


def build_loop_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sisyphusfy loop",
        description="Run the durable iteration loop",
    )
    parser.add_argument(
        "--task-path", "-T", required=True, help="Path to the task state file"
    )
    parser.add_argument(
        "--handoff-path", "-H", default=None, help="Path to the handoff file"
    )
    parser.add_argument(
        "--prompt-template", default="", help="Prompt template with {task_path} and {handoff_path} placeholders"
    )
    parser.add_argument(
        "--verification-command",
        nargs="*",
        default=None,
        help="Verification command to run after each iteration",
    )
    parser.add_argument(
        "--verification-timeout",
        type=float,
        default=30.0,
        help="Timeout for verification command in seconds",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=10, help="Maximum number of iterations"
    )
    parser.add_argument(
        "--agent-timeout", type=float, default=60.0, help="Timeout for agent in seconds"
    )
    parser.add_argument(
        "--working-directory", "-d", default=".", help="Working directory"
    )
    parser.add_argument(
        "--completion-strategy",
        choices=["markdown", "external"],
        default=None,
        help="Completion strategy: markdown (checkboxes) or external command",
    )
    parser.add_argument(
        "--check-command",
        nargs="*",
        default=None,
        help="External check command for completion strategy",
    )
    parser.add_argument(
        "--adapter",
        choices=["opencode", "codebuddy", "generic"],
        default=None,
        help="Agent adapter to use",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model to use with the adapter",
    )
    parser.add_argument(
        "--model-chain",
        nargs="*",
        default=None,
        help="Ordered list of models for fallback",
    )
    parser.add_argument(
        "--archive-command",
        nargs="*",
        default=None,
        help="Command to run for OpenSpec archive hook",
    )
    parser.add_argument(
        "--commit-command",
        nargs="*",
        default=None,
        help="Command to run for Git commit hook",
    )
    parser.add_argument(
        "--commit-allowed-files",
        nargs="*",
        default=None,
        help="Files allowed for Git commit staging",
    )
    parser.add_argument(
        "--workflow-type",
        choices=["markdown", "json", "external", "openspec"],
        default=None,
        help="Workflow adapter type",
    )
    parser.add_argument(
        "--workflow-task-path",
        default=None,
        help="Task path for workflow adapter",
    )
    parser.add_argument(
        "--workflow-state-path",
        default=None,
        help="State path for JSON workflow adapter",
    )
    parser.add_argument(
        "--workflow-predicate",
        default=None,
        help="Predicate for JSON workflow adapter",
    )
    parser.add_argument(
        "--workflow-check-command",
        nargs="*",
        default=None,
        help="Check command for external workflow adapter",
    )
    parser.add_argument(
        "--workflow-change-dir",
        default=None,
        help="Change directory for OpenSpec workflow adapter",
    )
    parser.add_argument(
        "--workflow-validation-command",
        nargs="*",
        default=None,
        help="Validation command for OpenSpec workflow adapter",
    )
    parser.add_argument(
        "--workflow-timeout",
        type=float,
        default=30.0,
        help="Timeout for workflow adapter commands",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print hook commands without executing"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print saved verification diagnostics"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true", help="Output structured JSON"
    )
    return parser


def build_init_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sisyphusfy init",
        description="Create project-local configuration",
    )
    parser.add_argument(
        "--project-dir", "-d", default=".", help="Project directory"
    )
    parser.add_argument(
        "--force", "-f", action="store_true", help="Overwrite existing configuration"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true", help="Output structured JSON"
    )
    return parser


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sisyphusfy run",
        description="Run a change with automatic workflow discovery",
    )
    parser.add_argument(
        "change", nargs="?", default=None, help="OpenSpec change name or task path"
    )
    parser.add_argument(
        "--project-dir", "-d", default=".", help="Project directory"
    )
    parser.add_argument(
        "--adapter", default=None, help="Agent adapter (default: config or opencode)"
    )
    parser.add_argument(
        "--model-chain", nargs="*", default=None, help="Ordered models for fallback"
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None, help="Maximum iterations"
    )
    parser.add_argument(
        "--agent-timeout", type=float, default=None, help="Agent timeout in seconds"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show planned actions without executing"
    )
    parser.add_argument(
        "--archive", action="store_true", help="Enable archive hook on completion"
    )
    parser.add_argument(
        "--commit", action="store_true", help="Enable commit hook on completion"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print saved verification diagnostics"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true", help="Output structured JSON"
    )
    return parser


def build_resume_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sisyphusfy resume",
        description="Continue from task and handoff files",
    )
    parser.add_argument(
        "--project-dir", "-d", default=".", help="Project directory"
    )
    parser.add_argument(
        "--adapter", default=None, help="Agent adapter"
    )
    parser.add_argument(
        "--model-chain", nargs="*", default=None, help="Ordered models for fallback"
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None, help="Maximum iterations"
    )
    parser.add_argument(
        "--agent-timeout", type=float, default=None, help="Agent timeout in seconds"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show planned actions without executing"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print saved verification diagnostics"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true", help="Output structured JSON"
    )
    return parser


def build_status_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sisyphusfy status",
        description="Show project state and task progress",
    )
    parser.add_argument(
        "--project-dir", "-d", default=".", help="Project directory"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true", help="Output structured JSON"
    )
    return parser


def build_doctor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sisyphusfy doctor",
        description="Check project configuration and prerequisites",
    )
    parser.add_argument(
        "--project-dir", "-d", default=".", help="Project directory"
    )
    parser.add_argument(
        "--json", dest="output_json", action="store_true", help="Output structured JSON"
    )
    return parser


def _parse_env_list(items: list[str] | None) -> dict[str, str]:
    if not items:
        return {}
    env: dict[str, str] = {}
    for item in items:
        key, _, value = item.partition("=")
        if not key:
            raise ValueError(f"invalid env format: {item!r}")
        env[key] = value
    return env


def _split_args(argv: list[str] | None) -> tuple[list[str], list[str]]:
    if argv is None:
        argv = sys.argv[1:]

    value_flags = {
        "--working-directory",
        "-d",
        "--prompt",
        "-p",
        "--timeout",
        "-t",
        "--env",
        "-e",
    }
    bool_flags = {"--dry-run", "--json", "--help", "-h"}
    known_flags = value_flags | bool_flags

    program_args: list[str] = []
    command: list[str] = []
    i = 0

    while i < len(argv):
        if argv[i] == "--":
            command = argv[i + 1 :]
            break
        if argv[i] not in known_flags:
            command = argv[i:]
            break
        if argv[i] in value_flags:
            program_args.append(argv[i])
            i += 1
            if i < len(argv):
                program_args.append(argv[i])
            i += 1
        else:
            program_args.append(argv[i])
            i += 1

    return program_args, command


def _run_single(argv: list[str] | None) -> None:
    program_args, command = _split_args(argv)
    parser = build_parser()
    args = parser.parse_args(program_args)

    if not command:
        parser.error("No command provided")

    env = _parse_env_list(args.env)

    result = run_agent(
        command,
        working_directory=args.working_directory,
        prompt=args.prompt,
        timeout=args.timeout,
        env=env if env else None,
        dry_run=args.dry_run,
    )

    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.classification.value == "dry_run":
            print(f"dry-run: {' '.join(result.command)}")
            print(f"  working directory: {result.working_directory}")
            if result.prompt:
                print(f"  prompt: {result.prompt}")
            if result.env:
                for k, v in result.env.items():
                    print(f"  env: {k}={v}")
        else:
            status = "OK" if result.exit_status == 0 else f"exit {result.exit_status}"
            print(f"[{status}] {' '.join(result.command)} ({result.duration_ms:.0f}ms)")
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)

    sys.exit(0 if result.classification.value == "success" else 1)


def _run_loop(argv: list[str] | None) -> None:
    from sisyphusfy.adapters import AdapterConfig
    from sisyphusfy.hooks import HookConfig, HookType
    from sisyphusfy.loop import (
        ExternalCommandCompletion,
        LoopConfig,
        MarkdownCheckboxCompletion,
        run_loop,
    )
    from sisyphusfy.workflows import WorkflowConfig

    if argv is None:
        argv = sys.argv[1:]

    loop_args = argv[1:] if argv and argv[0] == "loop" else argv

    parser = build_loop_parser()

    split_at = None
    for i, arg in enumerate(loop_args):
        if arg == "--":
            split_at = i
            break

    if split_at is not None:
        program_args = loop_args[:split_at]
        command = loop_args[split_at + 1 :]
    else:
        program_args = loop_args
        command = []

    args = parser.parse_args(program_args)

    if not command and not args.adapter:
        parser.error("No agent command provided (use -- to separate)")

    completion_strategy = None
    if args.completion_strategy == "markdown":
        completion_strategy = MarkdownCheckboxCompletion()
    elif args.completion_strategy == "external":
        if not args.check_command:
            parser.error("--check-command required with external completion strategy")
        completion_strategy = ExternalCommandCompletion(check_command=args.check_command)

    adapter_config = None
    if args.adapter:
        adapter_config = AdapterConfig(
            name=args.adapter,
            model=args.model,
            command=command,
        )

    completion_hooks = []
    if args.archive_command:
        completion_hooks.append(
            HookConfig(
                hook_type=HookType.ARCHIVE,
                command=args.archive_command,
                working_directory=args.working_directory,
                enabled=True,
            )
        )
    if args.commit_command:
        completion_hooks.append(
            HookConfig(
                hook_type=HookType.COMMIT,
                command=args.commit_command,
                working_directory=args.working_directory,
                allowed_files=args.commit_allowed_files or [],
                enabled=True,
            )
        )

    workflow_config = None
    if args.workflow_type:
        workflow_config = WorkflowConfig(
            adapter_type=args.workflow_type,
            task_path=args.workflow_task_path or args.task_path,
            state_path=args.workflow_state_path or "",
            predicate=args.workflow_predicate or "",
            check_command=args.workflow_check_command or [],
            change_dir=args.workflow_change_dir or "",
            validation_command=args.workflow_validation_command or [],
            timeout=args.workflow_timeout,
        )

    config = LoopConfig(
        agent_command=command,
        working_directory=args.working_directory,
        task_path=args.task_path,
        handoff_path=args.handoff_path,
        prompt_template=args.prompt_template,
        verification_command=args.verification_command,
        verification_timeout=args.verification_timeout,
        agent_timeout=args.agent_timeout,
        max_iterations=args.max_iterations,
        completion_strategy=completion_strategy,
        adapter_config=adapter_config,
        model_chain=args.model_chain or [],
        completion_hooks=completion_hooks,
        dry_run=args.dry_run,
        workflow_config=workflow_config,
        # Progress is streamed for human output only; JSON stays machine-readable.
        progress=None if args.output_json else StreamProgress(stream=sys.stderr),
    )

    result = run_loop(config)

    if args.output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        reason = result.stop_reason.value
        print(f"Loop stopped: {reason} after {result.iterations} iteration(s)")
        if result.run_records:
            last = result.run_records[-1]
            status = "OK" if last.result.exit_status == 0 else f"exit {last.result.exit_status}"
            print(f"  Last agent: [{status}] ({last.result.duration_ms:.0f}ms)")
        if result.adapter_error:
            print(f"  Adapter error: {result.adapter_error}")
        if result.completion_pipeline_result:
            for hook in result.completion_pipeline_result.hooks:
                print(f"  Hook {hook.hook_type.value}: {hook.status.value}")
        if args.verbose:
            from sisyphusfy.human import print_verification_log

            print_verification_log(result)

    sys.exit(0 if result.stop_reason.value == "complete" else 1)


def _run_init(argv: list[str]) -> None:
    from sisyphusfy.human import cmd_init

    parser = build_init_parser()
    args = parser.parse_args(argv)
    code = cmd_init(
        project_dir=args.project_dir,
        force=args.force,
        json_output=args.output_json,
    )
    sys.exit(code)


def _run_run(argv: list[str]) -> None:
    from sisyphusfy.human import cmd_run

    parser = build_run_parser()
    args = parser.parse_args(argv)
    code = cmd_run(
        project_dir=args.project_dir,
        change=args.change,
        json_output=args.output_json,
        dry_run=args.dry_run,
        archive=args.archive,
        commit=args.commit,
        verbose=args.verbose,
        max_iterations=args.max_iterations,
        adapter=args.adapter,
        model_chain=args.model_chain,
        agent_timeout=args.agent_timeout,
    )
    sys.exit(code)


def _run_resume(argv: list[str]) -> None:
    from sisyphusfy.human import cmd_resume

    parser = build_resume_parser()
    args = parser.parse_args(argv)
    code = cmd_resume(
        project_dir=args.project_dir,
        json_output=args.output_json,
        dry_run=args.dry_run,
        verbose=args.verbose,
        max_iterations=args.max_iterations,
        adapter=args.adapter,
        model_chain=args.model_chain,
        agent_timeout=args.agent_timeout,
    )
    sys.exit(code)


def _run_status(argv: list[str]) -> None:
    from sisyphusfy.human import cmd_status

    parser = build_status_parser()
    args = parser.parse_args(argv)
    code = cmd_status(
        project_dir=args.project_dir,
        json_output=args.output_json,
    )
    sys.exit(code)


def _run_doctor(argv: list[str]) -> None:
    from sisyphusfy.human import cmd_doctor

    parser = build_doctor_parser()
    args = parser.parse_args(argv)
    code = cmd_doctor(
        project_dir=args.project_dir,
        json_output=args.output_json,
    )
    sys.exit(code)


_SUBCOMMAND_HANDLERS = {
    "init": _run_init,
    "run": _run_run,
    "resume": _run_resume,
    "status": _run_status,
    "doctor": _run_doctor,
}


def _print_top_level_help() -> None:
    print("""usage: sisyphusfy [-h] [--json] [--dry-run] {init,run,resume,status,doctor,loop} ...

Project-agnostic supervisor for disposable AI-agent sessions.

subcommands:
  init        Create project-local configuration
  run         Run a change with automatic workflow discovery
  resume      Continue from task and handoff files
  status      Show project state and task progress
  doctor      Check project configuration and prerequisites
  loop        Run the durable iteration loop (advanced)

low-level:
  (no subcommand)  Run a single agent command (advanced)

examples:
  sisyphusfy init                          # create project config
  sisyphusfy run my-change                 # run an OpenSpec change
  sisyphusfy run my-change --dry-run       # preview planned actions
  sisyphusfy resume                        # continue durable loop
  sisyphusfy status                        # show project state
  sisyphusfy doctor                        # check prerequisites
  sisyphusfy -p "hello" -- echo "world"    # single agent invocation

Use 'sisyphusfy <subcommand> --help' for more information on a subcommand.""")


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    try:
        if argv and argv[0] in ("-h", "--help") and len(argv) == 1:
            _print_top_level_help()
            sys.exit(0)

        if argv and argv[0] in _SUBCOMMAND_HANDLERS:
            handler = _SUBCOMMAND_HANDLERS[argv[0]]
            handler(argv[1:])
        elif argv and argv[0] == "loop":
            _run_loop(argv)
        else:
            _run_single(argv)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(INTERRUPTED_EXIT_STATUS)


if __name__ == "__main__":
    main()
