# Proposal: Add test and lint gates to CI
## Why
Only .github/workflows/release.yml exists (triggered on v* tags); no workflow runs pytest or ruff on push/PR, even though there are 50+ test files and Ruff is configured but unenforced.
## What Changes
- Add .github/workflows/ci.yml running pytest and ruff (check + format --check) across Python 3.11/3.12 with coverage.

## Capabilities
### New Capabilities
- `ci-test-lint-gates`: tests and lint run automatically on every push/PR.

### Modified Capabilities
None.

## Impact
Affects: .github/workflows/ci.yml.
