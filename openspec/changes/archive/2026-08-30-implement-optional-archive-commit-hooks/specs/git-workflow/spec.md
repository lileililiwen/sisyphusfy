# Archive and Commit Hook Specification

## ADDED Requirements

### Requirement: Keep completion hooks opt-in

The system MUST NOT archive or commit unless the user explicitly enables the corresponding hook.

#### Scenario: Hooks are disabled

- **WHEN** a workflow reaches completion with default configuration
- **THEN** the system MUST report completion without invoking archive or commit commands

#### Scenario: Commit hook is enabled

- **WHEN** the user explicitly enables commit and verification has passed
- **THEN** the system MUST run the configured commit pipeline

### Requirement: Protect unrelated workspace changes

The system MUST stage only an explicit allowlist of files or generated change paths.

#### Scenario: Unrelated file exists

- **WHEN** an unrelated workspace file is present during an enabled commit
- **THEN** the system MUST leave that file unstaged

### Requirement: Provide safe preview and failure evidence

The system MUST support dry-run and MUST stop when an archive or commit hook fails.

#### Scenario: Dry-run is enabled

- **WHEN** completion hooks are enabled with dry-run
- **THEN** the system MUST display planned commands without changing the workspace

#### Scenario: Hook fails

- **WHEN** an enabled hook exits non-zero
- **THEN** the system MUST return a hook-failure result and MUST NOT invoke later hooks
