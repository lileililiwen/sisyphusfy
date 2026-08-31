## ADDED Requirements

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
