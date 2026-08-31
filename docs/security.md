# Command execution security

Sisyphusfy runs commands on your behalf. Every command it runs comes from your
configuration, which makes it executable user-controlled input. This document
states what runs, where it runs, and which safeguards apply.

## What executes

| Command | Source | When | Bounded by |
|---------|--------|------|------------|
| Agent | `adapter` (or the command after `--` for `sisyphusfy loop`) | Once per iteration | `agent_timeout` |
| Verification | `verification_command` (or auto-detected `pytest` / `make test` / `cargo test`) | Once per productive iteration, and before completion is accepted | `verification_timeout` |
| Workflow check | `external` workflow `check_command` | Before deciding completion | workflow `timeout` |
| Workflow validation | `openspec` workflow `validation_command` | When all tasks are checked | workflow `timeout` |
| Archive hook | `openspec archive` | After completion **and** verification succeed, only when `archive_enabled` or `--archive` | 30s hook timeout |
| Commit hook | `git commit` | After completion **and** verification succeed, only when `commit_enabled` or `--commit` | 30s hook timeout |

Each of these is arbitrary code with your privileges. Review them before you
enable them, exactly as you would review a `Makefile` target or a CI step.

## Safeguards

- **No shell.** Commands are argument lists passed to `subprocess.run` without
  `shell=True`. A configuration value cannot inject additional commands.
- **Explicit working directory.** Every command runs in the project directory
  selected with `--project-dir`. Relative paths resolve against that directory,
  so a project cannot reach outside itself by naming a relative path.
- **Timeouts.** Every subprocess has a timeout. A timeout is a structured stop
  reason (`timeout`), not a silent kill.
- **Verification before trust.** Completion is accepted only after verification
  passes, and verification runs at most once per productive iteration. Archive
  and commit hooks run only after both.
- **Commit allowlist.** The commit hook refuses to run without
  `commit_allowed_files`. Allowed paths are canonicalized and must resolve
  inside the working directory; a pattern that escapes is rejected with
  `PathEscapeError` and the hook fails.
- **Opt-in privileged operations.** Archive and commit are disabled by default.
  There is no push support and no privilege escalation; installers write to
  user-writable directories and require explicit opt-in for system-wide paths.
- **Dry-run.** `--dry-run` executes nothing: no agent, no verification command,
  no external completion check, no workflow validation, and no hook. Review
  dry-run output before enabling anything that writes.
- **Structured failures.** Failures are reported as data
  (`verification_failed`, `blocked`, `timeout`, `adapter_error`) instead of being
  retried blindly.

## Review checklist

Before enabling a command in a shared repository:

1. Read the command and every argument; remember it runs with the privileges of
   whoever runs Sisyphusfy.
2. Confirm the command cannot modify anything outside the project directory.
3. Set a timeout appropriate for the slowest legitimate run.
4. Keep `commit_allowed_files` as narrow as possible; never use `*` or `.`.
5. Run with `--dry-run` first and read the planned configuration.
6. Enable archive and commit only when verification is meaningful — a passing
   verification command is the only independent evidence the loop has.
