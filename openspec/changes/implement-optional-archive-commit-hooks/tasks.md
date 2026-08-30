# Tasks: Optional Archive and Commit Hooks

## 1. Testing

- [x] Test disabled hooks do not invoke external commands.
- [x] Test dry-run hook output and no workspace mutation.
- [x] Test explicit file allowlist staging with unrelated files present.
- [x] Test archive success and failure.
- [x] Test commit success, failure, and later-hook suppression.

## 2. Implementation

- [x] Define hook configuration and structured results.
- [x] Implement dry-run and confirmation policy.
- [x] Implement OpenSpec archive hook.
- [x] Implement allowlisted Git commit hook.
- [x] Implement completion pipeline and failure stop behavior.
- [x] Document security and non-Git usage.

## 3. Verification

- [x] Run focused tests twice.
- [x] Run lint, compile, and package checks.
- [x] Validate with strict OpenSpec validation.
