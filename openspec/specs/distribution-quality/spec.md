# distribution-quality Specification

## Purpose

Keep the Sisyphusfy distribution release gate honest and stable: the distribution main spec stays canonical, documentation tests stay archive-safe, and PowerShell verification reports skipped instead of passed when no runtime is present.
## Requirements
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

### Requirement: Keep release version metadata synchronized

Release version metadata MUST have one Python-side source of truth, and every artifact that repeats the version MUST be verified against it.

#### Scenario: Version bump

- **WHEN** the package version changes
- **THEN** the sdist/wheel version, npm manifest, npm launcher, and both installers MUST report the same version

#### Scenario: Tag and package version disagree

- **WHEN** a release tag does not match the packaged version
- **THEN** the release workflow MUST fail before publishing artifacts

### Requirement: Do not claim publication the release workflow does not perform

Roadmap and handoff claims MUST only mark a distribution channel as published when the release workflow actually publishes to it.

#### Scenario: Channel built but not uploaded

- **WHEN** CI builds an artifact for a channel but never uploads it
- **THEN** the roadmap MUST keep that channel's publication as an open release-readiness item and documentation MUST NOT describe it as available

