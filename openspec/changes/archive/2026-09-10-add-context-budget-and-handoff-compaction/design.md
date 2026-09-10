# Design: Add context budgets and handoff compaction

## Explore & Reuse

Reuse `render_handoff_prompt`, `LoopConfig`, `RunRecord`, diagnostics, workflow
snapshots, and existing fresh-process behavior. Keep handoff content in the
project workspace and keep provider-specific token usage behind an optional
adapter capability.

## Design

Before each invocation, Sisyphusfy will measure prompt and selected recovery
file sizes using a documented provider-neutral estimate. A configurable budget
will either reject an over-budget prompt before execution or apply an explicit
bounded reduction policy. The result records estimated input size, output size
when available, total estimates, budget, and whether truncation occurred.

The handoff contract will define bounded sections for completed work, current
state, blockers, next action, relevant files, and verification. Optional
compaction will rewrite only the configured handoff file through an explicit
command or adapter operation; it will never silently delete arbitrary history.

Adapters may report exact provider usage, but the core must label estimates and
must not pretend byte counts are billing tokens. Human status will show concise
budget state; JSON will expose machine-readable telemetry.

## Verification

Add tests for prompt budgets, deterministic estimation, truncation metadata,
handoff section limits, exact usage passthrough, dry-run behavior, and no
transcript replay. Run focused tests, full tests, lint/compile checks, and
strict OpenSpec validation.

## Approval gate

Implementation requires human approval of this design.
