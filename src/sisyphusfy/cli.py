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


def main(argv: list[str] | None = None) -> None:
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


if __name__ == "__main__":
    main()
