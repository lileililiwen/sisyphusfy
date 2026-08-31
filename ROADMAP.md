# Sisyphusfy Roadmap

## Phase 0 — Product contract

- [x] Choose the Sisyphusfy name and positioning.
- [x] Define fresh-session execution as the default.
- [x] Define project-agnostic configuration boundaries.
- [x] Choose the initial license: MIT.
- [x] Define the public configuration schema.
- [x] Define the agent adapter protocol.

## Phase 1 — Minimal runner

- [x] Implement a CLI that runs one agent iteration.
- [x] Accept an arbitrary agent command and pass the prompt through stdin or a configured argument.
- [x] Support working directory, timeout, environment, and exit-code capture.
- [x] Read optional instruction, task, and handoff files without assuming their names.
- [x] Add dry-run mode.
- [x] Add deterministic tests with fake agent commands.

## Phase 2 — Durable iteration loop

- [x] Detect incomplete task state through a configurable strategy.
- [x] Check that task state or handoff changed after a productive iteration.
- [x] Run an optional verification command after each iteration.
- [x] Stop on success, failure, timeout, unchanged state, or maximum iterations.
- [x] Write structured run results for humans and automation.
- [x] Keep handoff content outside the runner's generated logs.

## Phase 3 — Model and agent resilience

- [x] Add the OpenCode adapter.
- [x] Add the CodeBuddy adapter.
- [x] Add ordered model fallback.
- [x] Classify retryable provider failures separately from task failures.
- [x] Detect permission/choice blocking and stop with an actionable status.
- [x] Support user resumption without restoring conversation history.

## Phase 4 — Workflow integrations

- [x] Provide an OpenSpec example adapter.
- [x] Provide Markdown checklist and JSON task-state adapters.
- [x] Support configurable completion commands.
- [x] Add opt-in archive and commit hooks.
- [x] Add CI examples and a security review for command execution.

## Phase 5 — Public release

- [x] Publish package and standalone binary distribution options.
- [x] Document agent adapter authoring.
- [x] Add end-to-end examples for Python, Rust, JavaScript, Flutter, and .NET projects.
- [x] Add contribution guidelines and release automation.
- [ ] Publish the first stable release.
