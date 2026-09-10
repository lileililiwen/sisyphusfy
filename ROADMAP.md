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

- [x] Provide package and standalone binary distribution options (sdist/wheel, PyInstaller binaries, npm launcher, POSIX and PowerShell installers).
- [x] Document agent adapter authoring.
- [x] Add end-to-end examples for Python, Rust, JavaScript, Flutter, and .NET projects.
- [x] Add contribution guidelines and release automation.
- [x] Synchronize release version metadata: the package version is the source of truth, and the npm manifest, npm launcher, and installers are verified against it.
- [x] Publish the first stable release: GitHub Release v0.1.0 ships sisyphusfy-0.1.0-{linux-x86_64,darwin-x86_64,darwin-aarch64,win32-x86_64}.tar.gz plus SHA256SUMS.txt.
- [x] Register the PyPI project and trusted publisher; PyPI publication of `sisyphusfy==0.1.0` succeeds through the `publish-pypi` job.

## Phase 6 — Operational hardening

- [x] Tighten the agent adapter and fallback contracts: defensive `classify_failure` and `parse_error` so stale custom adapters never crash the supervisor or rotate models silently.
- [x] Bound subprocess lifecycle and output across every managed component (agent, verification, hook, workflow check) through a shared `run_command` primitive with component-labelled diagnostic logs and process-group cleanup.

## Phase 7 — Workspace integrity

- [x] Make workspace progress and completion reliable: opt-in source-change evidence, word-boundary blocked detection, structured `ConfigurationError` on malformed TOML, project-root path boundaries, and consistent uppercase/lowercase checklist parsing.
- [x] Add context budgets and handoff compaction: deterministic `chars/4` provider-neutral estimate, `reject`/`truncate` budget policy, bounded handoff sections, and `HandoffCompactor` that only rewrites the configured handoff file.

## Phase 8 — Long-run operability

- [x] Component-labelled diagnostic naming for every managed subprocess.
- [x] `--verification-timeout` override on `run` and `resume` with dry-run + JSON reporting of the effective value.
- [x] `sisyphusfy resume --inspect` reads the most recent diagnostic log without starting a new agent iteration.
- [x] Concise human failure summary with component, status, duration, log path, and inspect hint.
