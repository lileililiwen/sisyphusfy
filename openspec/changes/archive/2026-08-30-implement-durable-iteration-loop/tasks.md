# Tasks: Durable Iteration Loop

## 1. Testing

- [x] Test fresh process creation for each iteration.
- [x] Test Markdown and external-command completion strategies.
- [x] Test task/handoff snapshots and unchanged-state stopping.
- [x] Test verification success and failure classification.
- [x] Test timeout, max-iteration, and blocked stopping.
- [x] Test JSON loop results and bounded run records.

## 2. Implementation

- [x] Define loop configuration and result types.
- [x] Define state-adapter protocol and initial strategies.
- [x] Implement prompt rendering from configured files.
- [x] Implement the loop service by reusing `run_agent`.
- [x] Implement verification and stop-condition handling.
- [x] Add CLI command and configuration loading.

## 3. Verification

- [x] Run the focused tests twice.
- [x] Run lint, compile, and package checks.
- [x] Validate the change with strict OpenSpec validation.
