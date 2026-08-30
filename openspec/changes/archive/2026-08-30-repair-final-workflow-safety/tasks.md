# Tasks: Repair Final Workflow Safety and Specification Integrity

## 1. Testing

- [x] Add strict-validation coverage for canonical main spec headers.
- [x] Add dry-run tests proving agent, verifier, workflow, archive, and commit commands do not execute.
- [x] Add temporary-repository tests proving allowlisted staging and path-escape rejection.
- [x] Add fallback tests capturing every command and proving selected-model replacement.
- [x] Add fake-executable OpenCode and CodeBuddy argv/stdin contract tests.

## 2. Implementation

- [x] Normalize the archived agent-adapters and iteration-loop main specs.
- [x] Propagate dry-run through all loop and hook subprocess boundaries.
- [x] Implement canonical allowlisted staging and safe rejection rules.
- [x] Rebuild adapter commands per selected fallback model without continuation identifiers.
- [x] Update release documentation and handoff evidence.

## 3. Verification

- [x] Run the complete test suite twice.
- [x] Run lint, compile, and package checks in a writable environment.
- [x] Run CLI dry-run and fake-agent integration checks.
- [x] Run `openspec validate --all --strict`.
