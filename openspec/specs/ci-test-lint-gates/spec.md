# ci-test-lint-gates Specification

## Purpose
TBD - created by archiving change ci-test-lint-gates. Update Purpose after archive.
## Requirements
### Requirement: Test/lint in CI
CI SHALL run pytest and ruff on every push/PR.
#### Scenario: Push occurs
- **WHEN** a push is made
- **THEN** lint and tests run and fail on violations
#### Scenario: PR opened
- **WHEN** a pull request is opened
- **THEN** the same gates block merge on failure

