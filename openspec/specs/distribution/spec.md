# Distribution Specification

## Purpose

Publish Sisyphusfy releases with stable repository/website links, verified release artifacts, and explicit, safe installation paths across Python, npm, and POSIX/PowerShell installers.
## Requirements
### Requirement: Publish stable project links

Project documentation MUST identify `https://github.com/lileililiwen/sisyphusfy` as the source repository and `https://about.tooosall.uk/` as the public website when the domain is configured.

#### Scenario: User looks for source code

- **WHEN** a user reads the README or website
- **THEN** the user MUST find the canonical GitHub repository link

#### Scenario: Website is not configured

- **WHEN** the custom domain is unavailable
- **THEN** release documentation MUST still work through GitHub repository and release URLs

### Requirement: Provide verified release artifacts

Each published release MUST provide versioned artifacts and SHA-256 checksums over HTTPS.

#### Scenario: Download a release

- **WHEN** an installer selects a release version
- **THEN** it MUST download the pinned artifact and verify its checksum before installation

#### Scenario: Checksum fails

- **WHEN** an artifact checksum does not match
- **THEN** the installer MUST stop without installing or executing the artifact

### Requirement: Provide easy installation paths

The project MUST provide a Python installation path, an npm launcher, and POSIX/PowerShell installers without requiring users to clone the repository.

#### Scenario: npm installation

- **WHEN** a user runs `npm install -g sisyphusfy`
- **THEN** the installed command MUST launch the matching Sisyphusfy release without reimplementing runner logic

#### Scenario: POSIX installation

- **WHEN** a user runs the documented shell installer
- **THEN** it MUST install to a user-writable location by default and report any PATH action required

#### Scenario: Windows installation

- **WHEN** a user runs the documented PowerShell installer
- **THEN** it MUST install the matching release and report how to invoke it

### Requirement: Keep installation explicit and safe

Installers MUST use HTTPS, avoid implicit root elevation, support version selection, and provide dry-run or equivalent preview behavior.

#### Scenario: Default installation

- **WHEN** no installation directory is specified
- **THEN** the installer MUST select a user-writable directory and MUST NOT require administrator privileges

#### Scenario: Unsupported platform

- **WHEN** the platform or architecture has no published artifact
- **THEN** the installer MUST stop with supported-platform guidance

### Requirement: Document website deployment

The project MUST document GitHub Pages/custom-domain setup separately from repository hosting and MUST not require DNS changes to use the repository releases.

#### Scenario: Custom domain setup

- **WHEN** the maintainer configures `about.tooosall.uk`
- **THEN** documentation MUST describe repository Pages settings, DNS records, HTTPS, and domain verification

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
