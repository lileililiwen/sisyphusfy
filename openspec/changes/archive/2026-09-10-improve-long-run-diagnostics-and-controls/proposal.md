# Proposal: Improve long-run diagnostics and controls

## Why

Long-running use needs concise, correctly labelled diagnostics and practical
controls. Agent failures currently share verification log naming, and high-level
`run`/`resume` do not expose verification-timeout overrides even though real
projects often exceed the default.

## Scope

- Separate agent and verification diagnostic namespaces.
- Add verification-timeout overrides to high-level commands.
- Make resume/verbose output inspect existing evidence without rerunning work.
- Add concise run summaries and machine-readable diagnostic metadata.

## Non-goals

- No automatic retry of failed task work.
- No remote telemetry or upload.
- No change to verification semantics.
- No provider-specific UI.

This belongs in the CLI and diagnostics presentation layer, reusing structured
results from the loop.
