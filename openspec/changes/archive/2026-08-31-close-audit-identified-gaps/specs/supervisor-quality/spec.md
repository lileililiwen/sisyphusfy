## ADDED Requirements

### Requirement: Keep dry-run non-executing at every boundary

The supervisor MUST NOT execute an agent, verification command, external completion check, workflow validation command, archive hook, or commit hook when dry-run is enabled.

#### Scenario: External completion check in dry-run

- **WHEN** a loop uses an external completion strategy with dry-run enabled
- **THEN** the completion check MUST NOT execute and the result MUST identify the planned dry-run behavior

#### Scenario: Workflow validation in dry-run

- **WHEN** an OpenSpec or other workflow adapter has a validation command and dry-run is enabled
- **THEN** the validation command MUST NOT execute

### Requirement: Verify exactly once before accepting completion

The supervisor MUST run configured verification at most once for each productive iteration and MUST complete verification before invoking completion hooks or returning a complete result.

#### Scenario: Incomplete iteration

- **WHEN** an agent makes progress but leaves work incomplete
- **THEN** the configured verification command MUST run no more than once for that iteration

#### Scenario: Initially complete state

- **WHEN** task or workflow state is already complete and verification is configured
- **THEN** verification MUST succeed before archive or commit hooks run

#### Scenario: Failing verification

- **WHEN** verification fails
- **THEN** the supervisor MUST return verification failure and MUST NOT invoke completion hooks

### Requirement: Respect the selected project directory

High-level commands MUST use the selected project directory as the working directory for agents, verification, workflow commands, archive hooks, and commit hooks, and MUST resolve relative state paths consistently against that directory.

#### Scenario: Run from outside the project

- **WHEN** a user invokes a high-level command with `--project-dir /path/to/project` from another directory
- **THEN** every subprocess MUST execute against `/path/to/project`

#### Scenario: Relative hook paths

- **WHEN** a configured hook or workflow command uses relative paths
- **THEN** those paths MUST be interpreted relative to the selected project directory

### Requirement: Publish only truthful release targets

Release metadata, installers, npm platform detection, and CI MUST expose the same platform/architecture set, and CI MUST NOT label a binary with an architecture different from the binary it built.

#### Scenario: Unsupported target

- **WHEN** a target cannot be built for its advertised architecture
- **THEN** the target MUST be omitted or built with a verified native/cross-compilation process, and installers MUST not advertise it as available

### Requirement: Document public extension and execution contracts

The repository MUST document the public TOML configuration schema, agent adapter protocol, CI usage, supported ecosystem examples, and security implications of user-controlled command execution.

#### Scenario: Configure a project

- **WHEN** a user reads the configuration documentation
- **THEN** the user MUST find each supported field, type, default, precedence rule, and safety gate

#### Scenario: Author an adapter

- **WHEN** a user wants to add an agent adapter
- **THEN** the user MUST find the required protocol methods, registration path, command-input rules, model behavior, and failure classification contract

#### Scenario: Review command execution risk

- **WHEN** a user enables an agent, verification, workflow, archive, or commit command
- **THEN** documentation MUST identify that the command is executable user-controlled input and explain timeout, working-directory, dry-run, and commit-allowlist safeguards
