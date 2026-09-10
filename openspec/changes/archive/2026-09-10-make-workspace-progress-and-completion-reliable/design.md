# Design: Make workspace progress and completion reliable

## Explore & Reuse

Reuse workflow adapter snapshots/reload, `_changed`, existing read-only Git
inspection, `BLOCKED_MARKERS`, and TOML loading. Keep Git inspection optional and
keep task-format behavior inside state adapters.

## Design

Progress evidence will be configurable: task/handoff snapshots remain the
portable default, while a Git/workspace snapshot may be enabled to recognize
source changes. The result will state which evidence changed; it will not infer
that arbitrary file changes mean the task is complete.

Blocked output will use explicit line or structured-marker matching, with
configured markers treated as exact/pattern rules rather than unrestricted
substrings. Markdown checklist parsing will consistently accept supported case
variants.

Configured task, handoff, and workflow paths will be validated against the
selected project boundary unless an explicit trusted-outside-root mode is set.
Malformed TOML will return a structured configuration error identifying the
source file and parse problem; missing files may retain existing defaults.

## Verification

Add tests for code-only progress, clean/no-Git workspaces, false-positive
blockers, path escapes, uppercase checkboxes, malformed TOML, and JSON/human
diagnostics. Run focused tests, full tests, lint/compile checks, and strict
OpenSpec validation.

## Approval gate

Implementation requires human approval of this design.
