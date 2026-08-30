# workflow-safety Specification

## Purpose
TBD - created by archiving change repair-final-workflow-safety. Update Purpose after archive.
## Requirements
### Requirement: Keep archived main specifications valid

The repository MUST keep every active main capability specification in the canonical format with `## Purpose` and `## Requirements` sections, and MUST preserve requirement scenarios when syncing a change.

#### Scenario: Validate all main specs

- **WHEN** the full OpenSpec validator runs in strict mode
- **THEN** every main capability specification MUST pass validation

### Requirement: Make loop dry-run non-executing

The loop MUST propagate dry-run to every external process boundary and MUST NOT execute any agent, verification, workflow-check, archive, or commit command in dry-run mode.

#### Scenario: Dry-run with a mutating fake agent

- **WHEN** loop dry-run is enabled and the configured agent would create a marker file
- **THEN** the marker file MUST NOT be created

#### Scenario: Dry-run with completion hooks

- **WHEN** archive or commit hooks are enabled with dry-run
- **THEN** the hooks MUST report planned execution without invoking their commands

### Requirement: Enforce commit path allowlists

An enabled commit hook MUST canonicalize and stage only configured paths inside the working directory, and MUST reject empty or escaping allowlists.

#### Scenario: Allowed and unrelated files

- **WHEN** the allowlist names one changed file and an unrelated changed file exists
- **THEN** only the allowed file may be staged for the commit

#### Scenario: Path escapes workspace

- **WHEN** an allowlist contains a path outside the configured working directory
- **THEN** the hook MUST fail before staging or committing

### Requirement: Apply the selected fallback model

Each model fallback attempt MUST construct a fresh command containing the selected model and MUST NOT retain a previous model argument or session identifier.

#### Scenario: First model fails

- **WHEN** the first configured model returns a retryable provider failure
- **THEN** the next invocation MUST contain only the next model selection and preserve the workspace state

#### Scenario: Non-retryable failure

- **WHEN** an attempt returns a non-retryable failure
- **THEN** the system MUST stop without trying another model

### Requirement: Verify named adapter command contracts

The system MUST test OpenCode and CodeBuddy adapters using fake executables that capture arguments and stdin.

#### Scenario: OpenCode adapter test

- **WHEN** a fake OpenCode executable receives an adapter invocation
- **THEN** the captured command MUST use fresh non-interactive execution and pass the prompt and selected model

#### Scenario: CodeBuddy adapter test

- **WHEN** a fake CodeBuddy executable receives an adapter invocation
- **THEN** the captured command MUST use the documented non-interactive form and pass the prompt and selected model

