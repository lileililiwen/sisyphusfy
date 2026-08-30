# Sisyphusfy Roadmap

## Phase 0 — Product contract

- [x] Choose the Sisyphusfy name and positioning.
- [x] Define fresh-session execution as the default.
- [x] Define project-agnostic configuration boundaries.
- [x] Choose the initial license: MIT.
- [ ] Define the public configuration schema.
- [ ] Define the agent adapter protocol.

## Phase 1 — Minimal runner

- [ ] Implement a CLI that runs one agent iteration.
- [ ] Accept an arbitrary agent command and pass the prompt through stdin or a configured argument.
- [ ] Support working directory, timeout, environment, and exit-code capture.
- [ ] Read optional instruction, task, and handoff files without assuming their names.
- [ ] Add dry-run mode.
- [ ] Add deterministic tests with fake agent commands.

## Phase 2 — Durable iteration loop

- [ ] Detect incomplete task state through a configurable strategy.
- [ ] Check that task state or handoff changed after a productive iteration.
- [ ] Run an optional verification command after each iteration.
- [ ] Stop on success, failure, timeout, unchanged state, or maximum iterations.
- [ ] Write structured run results for humans and automation.
- [ ] Keep handoff content outside the runner's generated logs.

## Phase 3 — Model and agent resilience

- [ ] Add the OpenCode adapter.
- [ ] Add the CodeBuddy adapter.
- [ ] Add ordered model fallback.
- [ ] Classify retryable provider failures separately from task failures.
- [ ] Detect permission/choice blocking and stop with an actionable status.
- [ ] Support user resumption without restoring conversation history.

## Phase 4 — Workflow integrations

- [ ] Provide an OpenSpec example adapter.
- [ ] Provide Markdown checklist and JSON task-state adapters.
- [ ] Support configurable completion commands.
- [ ] Add opt-in archive and commit hooks.
- [ ] Add CI examples and a security review for command execution.

## Phase 5 — Public release

- [ ] Publish package and standalone binary distribution options.
- [ ] Document agent adapter authoring.
- [ ] Add end-to-end examples for Python, Rust, JavaScript, Flutter, and .NET projects.
- [ ] Add contribution guidelines and release automation.
- [ ] Publish the first stable release.
