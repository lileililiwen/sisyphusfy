# Design: Close audit safety and diff gaps

## Explore & Reuse

- Reuse `runner.run_agent` as the only agent/verifier subprocess boundary.
- Reuse `format_command`, `RunResult`, and existing bounded diagnostic patterns.
- Reuse the hook pipeline and explicit `commit_allowed_files` configuration.
- Keep Git-specific inspection in a small adapter/module; the loop remains
  usable for non-Git projects.
- Preserve the current stdout/stderr split: human progress stays on stderr and
  machine-readable results stay on stdout.

## Process cleanup

On POSIX, launch each bounded subprocess in a new process session and terminate
the entire process group on timeout or interrupt. On Windows, use the platform
process-group creation flag and terminate the launched group using the supported
subprocess API. If group cleanup is unavailable, retain direct-child cleanup and
report that limitation in the structured result rather than claiming complete
cleanup. Reader threads must still drain with the existing grace period.

## Commit safety

Before staging, inspect the repository index. The hook may proceed only when
there are no pre-existing staged paths outside the canonicalized allowlist. It
must also apply a timeout to `git add` and fail when staging returns non-zero.
The existing path escape checks remain in force. The hook never clears or
overwrites the user's index.

## Git inspection

Add a read-only Git adapter that runs bounded argument-list commands in the
selected project directory: porcelain status, diff stat, and unified diff. It
returns a structured snapshot containing repository availability, branch/status
entries, changed-file counts, and bounded diff text with an explicit truncation
flag. Missing Git or a non-repository directory is a structured unavailable
state, not an exception.

Expose this through `sisyphusfy status --diff` and a new `sisyphusfy diff`
command, each with `--stat`, `--staged`, and `--json` options. Default output
shows a concise file summary; full patch output is opt-in and capped. Existing
status output remains valid when `--diff` is omitted.

## Verification

Add tests first for descendant cleanup, unrelated staged-file rejection,
`git add` failure/timeout, Git snapshot parsing, missing-repository behavior,
diff truncation, and CLI human/JSON output. Run focused tests, the full test
suite, Ruff, compile checks, strict OpenSpec validation, and `git diff --check`.
