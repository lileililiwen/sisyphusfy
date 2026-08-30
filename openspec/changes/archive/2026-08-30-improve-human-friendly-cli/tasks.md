# Tasks: Human-Friendly CLI

## 1. Testing

- [x] Test `init` creation, existing-config protection, and defaults.
- [x] Test `run <change>` OpenSpec discovery and generic workflow fallback.
- [x] Test `resume`, `status`, and `doctor` behavior in complete, incomplete, and blocked projects.
- [x] Test configuration precedence and command-line overrides.
- [x] Test human output for progress, fallback, blockers, and next actions.
- [x] Test JSON output remains stable and machine-readable.
- [x] Test high-level dry-run never invokes agent, verification, or hooks.
- [x] Test archive and commit remain disabled without explicit flags.

## 2. Implementation

- [x] Define project configuration schema and precedence.
- [x] Implement project discovery and `init`.
- [x] Implement `run <change>` and `resume` as thin loop configuration layers.
- [x] Implement read-only `status` and `doctor` diagnostics.
- [x] Implement human-readable progress and blocker rendering.
- [x] Preserve low-level command compatibility and JSON output.
- [x] Update README with the human-friendly workflow.

## 3. Verification

- [x] Run the complete suite twice.
- [x] Run lint, compile, and package checks.
- [x] Run CLI smoke tests in temporary OpenSpec and generic projects.
- [x] Validate with `openspec validate improve-human-friendly-cli --strict`.
