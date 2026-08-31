# Distribution Specification

## ADDED Requirements

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
