# Design: Harden agent adapter and fallback contracts

## Explore & Reuse

Reuse `AgentAdapter`, `FailureClass`, `try_fallback`, `_run_iteration`,
`RunResult`, and the existing adapter contract tests. Keep command construction
as the adapter responsibility and keep retry policy in `try_fallback`.

## Design

Each attempt will expose one canonical command list. The generic adapter will
distinguish its complete configured command from adapter-specific extra
arguments; no argument may be appended twice. Named adapters will continue to
construct a fresh command for every model.

Failure classification will receive combined bounded stdout and stderr, while
structured error parsing will retain the complete bounded diagnostic input.
Provider/process retry markers remain conservative and task-level non-zero
exits remain non-retryable.

Every attempt records selected model, command, exit status, classification, and
whether fallback advanced. A fallback attempt must never reuse a previous model
flag or session identifier.

## Verification

Add regression tests for stdout-only quota errors, generic commands with
arguments, fresh model replacement, unsupported models, and non-retryable
failures. Run focused tests, the full suite, Ruff/compile checks, and strict
OpenSpec validation.

## Approval gate

Implementation requires human approval of this design.
