## ADDED Requirements

### Requirement: Run completion checks in the selected working directory

The supervisor MUST run a completion check command in the same working directory it uses for agents, verification, workflow validation, and completion hooks, unless the check declares its own directory.

#### Scenario: Low-level loop with a selected directory

- **WHEN** a low-level loop runs with `-d /path/to/project` and an external completion strategy
- **THEN** the completion check command MUST execute in `/path/to/project`

#### Scenario: Explicit completion check directory

- **WHEN** a completion strategy is constructed with its own working directory
- **THEN** the supervisor MUST use that directory instead of the loop working directory

### Requirement: Report missing commands as structured failures

The supervisor MUST report a missing agent, verification, or completion-check executable as a `command_not_found` result that names the command instead of raising an unhandled exception.

#### Scenario: Missing agent command

- **WHEN** the configured agent executable does not exist
- **THEN** the run result MUST be classified `command_not_found` and the loop MUST stop with an actionable message naming the command

#### Scenario: Missing verification command

- **WHEN** the configured verification executable does not exist
- **THEN** the loop MUST stop with `command_not_found` and MUST NOT invoke completion hooks

#### Scenario: Missing completion check command

- **WHEN** an external completion check or workflow command does not exist
- **THEN** the loop MUST stop with `command_not_found` and MUST NOT invoke completion hooks
