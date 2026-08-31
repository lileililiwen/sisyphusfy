# Distribution Specification

## ADDED Requirements

### Requirement: Tagged releases publish the npm launcher

The tagged release workflow MUST publish the package rooted at `npm/` to the
public npm registry after the GitHub release is created.

#### Scenario: A release tag is pushed

- **WHEN** a `v*` tag passes the artifact and GitHub release jobs
- **THEN** the npm publication job runs `npm publish --access public` from `npm/`
- **AND** the job authenticates with npm trusted publishing using OIDC

### Requirement: npm publication is tokenless

The release workflow MUST NOT require or embed a long-lived npm authentication
token for publication.

#### Scenario: The workflow is inspected

- **WHEN** the release workflow is loaded
- **THEN** the npm publication job grants `id-token: write`
- **AND** no `NPM_TOKEN` or `NODE_AUTH_TOKEN` is configured
