# Design: Render commands unambiguously

## Explore & Reuse

- Reuse the existing display sites rather than adding new output. The change is
  one formatter plus the call sites that already render a command.
- Reuse `shlex.join()` from the standard library. It quotes only what needs
  quoting, so `["dotnet", "test", "App.sln"]` still renders as
  `dotnet test App.sln` and no existing output churns.
- Keep the formatter beside `RunResult`, the type that already carries the
  argument list, so the log writer, the human reporters, and the low-level CLI
  can all import it without a new module or a new dependency direction. `result`
  imports nothing from the package, so no cycle is introduced.
- Do not touch execution. `run_agent()` keeps passing the list to
  `subprocess.Popen` with no shell; the formatter is display-only and is never
  fed back into a process.
- Do not touch structured output. `to_dict()` keeps `command` as a list, so
  JSON consumers are unaffected and cannot be broken by display quoting.

## Behavior

One function renders an argument list for humans:

```python
format_command(["opencode", "run", "Read /tmp/tasks.md and any handoff"])
# opencode run 'Read /tmp/tasks.md and any handoff'
format_command(["dotnet", "test", "App.sln"])
# dotnet test App.sln
```

It is used at every site that currently joins with spaces: the diagnostic log
header, the agent-failure report, the timeout report, the verification status
line, `doctor` and dry-run verification descriptions, and the low-level
single-command result line. An empty command renders as an empty string, which
is what the existing sites would have produced anyway.

## Error handling and safety

Rendering never raises for the inputs it receives: command lists are strings by
construction. Because the formatter is display-only, a quoting bug cannot
change what executes, and the no-shell guarantee documented in `docs/security.md`
is untouched. The diagnostic log continues to record no environment values or
prompts beyond the command itself, which was already the case.

## Verification

Add tests that a multi-word argument is quoted in the diagnostic log, in the
agent-failure report, and in the verification status line; that a simple command
is unchanged; and that an empty command renders safely. Run focused tests, the
full suite, lint/compile checks, and strict OpenSpec validation.
