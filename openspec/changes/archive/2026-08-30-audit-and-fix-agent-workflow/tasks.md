# Tasks: Audit and Fix the Agent Workflow

## 1. Testing

- [x] Add adapter argv tests for valid fresh OpenCode and CodeBuddy invocations.
- [x] Add tests proving no continuation/session identifiers are passed.
- [x] Add mutable-file tests proving Markdown, JSON, and OpenSpec adapters reload state.
- [x] Add loop tests proving verification runs before completion and hooks.
- [x] Add tests for the default token-efficient prompt.
- [x] Add blocked-signal tests across stdout, stderr, and structured output, plus ordinary failure negatives.
- [x] Add temporary-repository tests proving commit allowlists cannot stage unrelated files.

## 2. Implementation

- [x] Correct OpenCode and CodeBuddy adapter command construction.
- [x] Remove or invalidate stale workflow-adapter caches between observations.
- [x] Reorder loop verification and completion handling.
- [x] Add the default prompt and configurable blocked-signal policy.
- [x] Enforce commit allowlists before running commit commands.
- [x] Update README, ROADMAP, and HANDOFF with the corrected workflow contract.

## 3. Verification

- [x] Run the complete test suite twice.
- [x] Run lint, compile, and package checks in a writable environment.
- [x] Run CLI smoke tests with fake agents and configured OpenSpec workflows.
- [x] Validate this change with `openspec validate audit-and-fix-agent-workflow --strict`.
