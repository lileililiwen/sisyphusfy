# Design: Repair Distribution Release Gates

## Explore & Reuse

Reuse the existing `distribution` main spec, archived change records, README links, installer tests, and release workflow. Correct metadata/test references in place; do not duplicate installer logic.

## Corrections

1. Convert `openspec/specs/distribution/spec.md` to canonical `## Purpose` and `## Requirements` sections while preserving all five requirements and scenarios.
2. Make link tests read the stable README or canonical main spec, not an active change directory that is removed after archive.
3. Add a supported PowerShell CI job or documented verification environment. The check must distinguish unavailable PowerShell from script failure.
4. Keep release checks independent of local cache, virtual environment, and transient build directories.

## Verification

Run full OpenSpec validation, the complete test suite twice, Ruff, compileall, package build, shell syntax check, and PowerShell checks where the runtime is available. Do not claim PowerShell success when the runtime is unavailable.
