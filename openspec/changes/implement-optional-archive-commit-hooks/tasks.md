# Tasks: Optional Archive and Commit Hooks

## 1. Testing

- [ ] Test disabled hooks do not invoke external commands.
- [ ] Test dry-run hook output and no workspace mutation.
- [ ] Test explicit file allowlist staging with unrelated files present.
- [ ] Test archive success and failure.
- [ ] Test commit success, failure, and later-hook suppression.

## 2. Implementation

- [ ] Define hook configuration and structured results.
- [ ] Implement dry-run and confirmation policy.
- [ ] Implement OpenSpec archive hook.
- [ ] Implement allowlisted Git commit hook.
- [ ] Implement completion pipeline and failure stop behavior.
- [ ] Document security and non-Git usage.

## 3. Verification

- [ ] Run focused tests twice.
- [ ] Run lint, compile, and package checks.
- [ ] Validate with strict OpenSpec validation.
