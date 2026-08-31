# Proposal: Simplify verification failures

## Why

Sisyphusfy currently treats an empty `verification_command` as permission to
auto-detect a command from a short executable-name list. In a .NET repository
this can select `make test` merely because `make` exists, even when no Makefile
or `test` target exists. The resulting human output says only that verification
failed, while the captured verification stdout and stderr are not returned in
the loop result.

This makes a normal smoke test difficult to configure and makes a failure hard
to diagnose without manually guessing and rerunning the command.

## What changes

- Make auto-detection inspect repository markers and command support before
  selecting a verification command, with deterministic precedence and a safe
  no-command result when no supported verifier is identified.
- Add built-in detection for common project ecosystems, including .NET,
  Python, Rust, JavaScript, and Flutter, while keeping explicit configuration
  authoritative.
- Persist bounded verification stdout and stderr in a local Sisyphusfy log
  file for each run or iteration.
- Keep default human output concise but include the verifier, exit status, and
  log path; provide explicit commands or flags to inspect full diagnostics.
- Include structured verification evidence in JSON output without exposing
  full logs by default.
- Make `doctor` show the resolved verification source and command before a run.

## Non-goals

- No execution of shell strings, arbitrary project scripts, or package-manager
  installation commands during detection.
- No replacement for a project-specific verification command supplied by the
  user.
- No automatic retry of a failed verification command.
- No changes to agent prompts, task state semantics, archive hooks, or commit
  authorization.
- No claim that a passing unit-test command is a browser, API, database, or
  production smoke test.

## Success criteria

An OpenLearning-style .NET repository resolves to its solution test command,
an unrelated installed executable cannot cause `make test` to be selected, a
failed verifier produces a concise actionable message and a discoverable log,
JSON identifies the verification result, and explicit configuration remains
the highest-precedence choice. Focused tests and strict OpenSpec validation
must pass.
