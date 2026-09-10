# Command execution security

Sisyphusfy runs commands on your behalf. Every command it runs comes from your
configuration, which makes it executable user-controlled input. This document
states what runs, where it runs, and which safeguards apply.

## What executes

| Command | Source | When | Bounded by |
|---------|--------|------|------------|
| Agent | `adapter` (or the command after `--` for `sisyphusfy loop`) | Once per iteration | `agent_timeout` |
| Verification | `verification_command`, else marker-based discovery | Once per productive iteration, and before completion is accepted | `verification_timeout` |
| Workflow check | `external` workflow `check_command` | Before deciding completion | workflow `timeout` |
| Workflow validation | `openspec` workflow `validation_command` | When all tasks are checked | workflow `timeout` |
| Archive hook | `openspec archive` | After completion **and** verification succeed, only when `archive_enabled` or `--archive` | 30s hook timeout |
| Commit hook | `git commit` | After completion **and** verification succeed, only when `commit_enabled` or `--commit` | 30s hook timeout |

Each of these is arbitrary code with your privileges. Review them before you
enable them, exactly as you would review a `Makefile` target or a CI step.

## Safeguards

- **No shell.** Commands are argument lists passed to `subprocess.run` without
  `shell=True`. A configuration value cannot inject additional commands.
- **Display quoting.** Where a command is shown (diagnostic logs, the
  human-readable result, `doctor`, and dry-run), each argument is rendered with
  shell-style quoting via `shlex.join`. A multi-word argument such as the default
  agent prompt appears as one quoted token, so argument boundaries are visible and
  the line does not look like a malformed, unquoted command. This is display-only
  and never fed back into a process.
- **Explicit working directory.** Every command runs in the project directory
  selected with `--project-dir`. Relative paths resolve against that directory,
  so a project cannot reach outside itself by naming a relative path.
- **Timeouts.** Every subprocess has a timeout. A timeout is a structured stop
  reason (`timeout`), not a silent kill. On POSIX the runner launches the
  child in its own process session, signals the entire group on timeout or
  interrupt, and reaps the launched process before returning, so a
  long-lived descendant cannot outlive the loop. The timeout report names
  the component, the limit with explicit units, and the diagnostic log
  path.
- **Safe interruption.** Ctrl-C stops the running child, terminates it, and
  returns a structured `interrupted` result. Task and handoff files are left
  untouched and archive and commit hooks are skipped, so an interrupt can never
  publish work that was not verified.
- **Verification before trust.** Completion is accepted only after verification
  passes, and verification runs at most once per productive iteration. Archive
  and commit hooks run only after both.
- **Commit allowlist.** The commit hook refuses to run without
  `commit_allowed_files`. Allowed paths are canonicalized and must resolve
  inside the working directory; a pattern that escapes is rejected with
  `PathEscapeError` and the hook fails. Before staging, the hook inspects the
  existing index and refuses to run when it contains a pre-staged path that is
  not in the allowlist -- a failing allowlist check never clears or
  overwrites the user's index. `git add` is bounded by a timeout and a
  non-zero exit is reported as a structured failure that prevents the commit
  command from running.
- **Opt-in privileged operations.** Archive and commit are disabled by default.
  There is no push support and no privilege escalation; installers write to
  user-writable directories and require explicit opt-in for system-wide paths.
- **Dry-run.** `--dry-run` executes nothing: no agent, no verification command,
  no external completion check, no workflow validation, and no hook. Review
  dry-run output before enabling anything that writes.
- **Read-only detection.** Verification discovery inspects project markers and
  executable availability; it never runs a candidate verifier to see whether it
  works, and an executable without its project marker selects nothing.
- **Read-only Git inspection.** `sisyphusfy status --diff` and the dedicated
  `sisyphusfy diff` subcommand run only `git status`, `git diff`, and
  `git diff --stat`, all bounded by a timeout. The diff payload is capped
  (default 50 KB) and the structured result carries a `truncated` flag plus
  the change statistics. A missing `git` executable or a non-repository
  directory is reported as a structured unavailable state with a `reason`
  (for example, `not_a_repository`), never raised as an exception. Nothing
  is staged, committed, or pushed by these commands.
- **Bounded diagnostics.** Verification output is written to
  `<project_dir>/.sisyphusfy/logs/` with the 20 newest files kept. Logs are
  local, are never committed or archived by Sisyphusfy, and contain no
  environment values. Default output and JSON stay concise; full streams require
  `--verbose` or reading the log.
- **Structured failures.** Failures are reported as data (`verification_failed`,
  `agent_failed`, `blocked`, `timeout`, `command_not_found`, `adapter_error`,
  `interrupted`) instead of being retried blindly or surfacing as an unhandled
  exception. A
  missing agent, verification, or completion command names the command that
  could not be executed.
- **Progress stays out of the result.** Live progress and heartbeats are written
  to stderr, so the human result and `--json` output on stdout remain the
  authoritative record. Streaming does not disable capture, timeout enforcement,
  argument isolation, or output bounds.

## Review checklist

Before enabling a command in a shared repository:

1. Read the command and every argument; remember it runs with the privileges of
   whoever runs Sisyphusfy.
2. Confirm the command cannot modify anything outside the project directory.
3. Set a timeout appropriate for the slowest legitimate run.
4. Keep `commit_allowed_files` as narrow as possible; never use `*` or `.`.
5. Run with `--dry-run` first and read the planned configuration.
6. Enable archive and commit only when verification is meaningful — a passing
   verification command is the only independent evidence the loop has, and it
   proves only that the command passed, not that the product works end to end.
