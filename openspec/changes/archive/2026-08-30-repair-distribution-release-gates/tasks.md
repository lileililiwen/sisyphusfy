# Tasks: Repair Distribution Release Gates

## 1. Testing

- [x] Add canonical-header validation for the distribution main spec.
- [x] Update link tests to use stable README/spec paths after archive.
- [x] Add supported PowerShell syntax and installer fixture checks.
- [x] Add explicit skipped reporting for unavailable PowerShell.
- [x] Add clean-environment packaging and release metadata checks.

## 2. Implementation

- [x] Normalize the distribution main spec.
- [x] Repair archive-safe documentation test paths.
- [x] Add portable PowerShell verification to release checks.
- [x] Update handoff and release documentation with evidence.

## 3. Verification

- [x] Run the complete test suite twice.
- [x] Run Ruff, compileall, shell syntax, and package checks.
- [x] Run PowerShell checks or record an explicit skipped result.
- [x] Run `openspec validate --all --strict`.
