# Tasks

## 1. Testing

- [ ] Add runner tests proving timeout/interrupt cleanup uses process-group
  semantics where supported and preserves structured classifications.
- [ ] Add hook tests proving unrelated pre-staged paths reject the commit,
  staging failures reject the commit, and staging is bounded by a timeout.
- [ ] Add Git adapter tests for status parsing, staged/unstaged diff selection,
  truncation metadata, and non-Git directories.
- [ ] Add CLI tests for `status --diff`, `diff`, `--stat`, `--staged`, and JSON
  output.

## 2. Implementation

- [ ] Implement cross-platform bounded process-group launch and cleanup in the
  runner without changing normal command argument handling.
- [ ] Make commit-index validation and `git add` failure/timeout handling fail
  closed without clearing the user's index.
- [ ] Implement the read-only Git inspection adapter with bounded output and
  structured unavailable/error results.
- [ ] Wire the adapter into the human CLI while preserving existing status and
  JSON behavior when diff inspection is not requested.

## 3. Verification and documentation

- [ ] Document the new diff/status commands and their output limits.
- [ ] Run focused tests, the full suite, Ruff, compile checks, strict OpenSpec
  validation, and `git diff --check`.
- [ ] Archive this change only after all verification passes.
