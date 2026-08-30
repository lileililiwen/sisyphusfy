from __future__ import annotations

import argparse
import json
import sys

from sisyphusfy.runner import run_agent


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
    from sisyphusfy.loop import (
        ExternalCommandCompletion,
        LoopConfig,
        MarkdownCheckboxCompletion,
        run_loop,
    )

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

    sys.exit(0 if result.stop_reason.value == "complete" else 1)


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "loop":
        _run_loop(argv)
    else:
        _run_single(argv)


if __name__ == "__main__":
    main()
