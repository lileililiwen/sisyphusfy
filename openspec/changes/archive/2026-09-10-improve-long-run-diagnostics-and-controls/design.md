# Design: Improve long-run diagnostics and controls

## Explore & Reuse

Reuse `VerificationEvidence`, `print_verification_log`, human command parsers,
progress sinks, and JSON result serialization. Keep execution behavior in the
loop and make the CLI a thin presentation/configuration layer.

## Design

Diagnostic records will carry a component (`agent`, `verification`, `workflow`,
or `hook`) and use matching filenames. Existing logs remain readable through a
compatibility lookup. `--verbose` on `resume` will inspect saved evidence and
will not implicitly start a new iteration when the user requested inspection.

High-level `run` and `resume` will accept `--verification-timeout`, show the
effective value in dry-run output, and include it in JSON configuration/evidence.
Human output will summarize iteration, component, status, duration, next action,
and diagnostic path; detailed streams remain opt-in.

## Verification

Add CLI tests for timeout overrides, dry-run display, log labels, verbose
inspection, JSON shape, missing logs, and concise failure output. Run focused
tests, full tests, lint/compile checks, and strict OpenSpec validation.

## Approval gate

Implementation requires human approval of this design.
