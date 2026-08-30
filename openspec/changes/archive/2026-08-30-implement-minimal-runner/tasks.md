# Tasks: Minimal Runner

## 1. Testing

- [x] Add unit tests for command construction and argument preservation.
- [x] Add process tests for successful exit and captured output.
- [x] Add process tests for non-zero exit and timeout classification.
- [x] Add tests for prompt delivery, working directory, and environment propagation.
- [x] Add a dry-run test that proves no subprocess starts.

## 2. Implementation

- [x] Create the Python package and typed result model.
- [x] Implement the generic subprocess runner with mandatory timeout.
- [x] Implement CLI parsing for working directory, command, prompt, timeout, and dry-run.
- [x] Add human-readable and JSON result output.
- [x] Add documentation and usage examples.

## 3. Verification

- [x] Run the focused test suite twice.
- [x] Run formatting, linting, and packaging checks.
- [x] Validate this change with `openspec validate implement-minimal-runner --strict`.
