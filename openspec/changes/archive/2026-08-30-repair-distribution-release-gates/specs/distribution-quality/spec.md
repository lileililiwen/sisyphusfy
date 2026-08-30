# Distribution Release Gate Specification

## ADDED Requirements

### Requirement: Keep the distribution main spec canonical

The distribution main specification MUST use `## Purpose` and `## Requirements` and MUST preserve all accepted distribution requirements after archive.

#### Scenario: Full strict validation

- **WHEN** `openspec validate --all --strict` runs
- **THEN** the distribution specification MUST pass without delta-only headers

### Requirement: Keep documentation tests archive-safe

Documentation tests MUST validate stable repository artifacts or canonical specs and MUST NOT require an active archived change directory.

#### Scenario: Change is archived

- **WHEN** a distribution change has moved to `openspec/changes/archive/`
- **THEN** link tests MUST continue to locate and validate the canonical project links

### Requirement: Report PowerShell verification honestly

The release checks MUST run PowerShell installer verification when PowerShell is available and MUST report an explicit skipped result when it is unavailable.

#### Scenario: PowerShell available

- **WHEN** a supported PowerShell runtime is available
- **THEN** installer syntax and fixture tests MUST run and pass

#### Scenario: PowerShell unavailable

- **WHEN** no supported PowerShell runtime is available
- **THEN** the release report MUST identify the check as skipped, not passed
