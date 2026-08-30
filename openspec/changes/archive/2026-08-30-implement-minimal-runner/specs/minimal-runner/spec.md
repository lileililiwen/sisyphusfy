# Minimal Runner Specification

## ADDED Requirements

### Requirement: Run one configured agent invocation

The system MUST execute one configured agent command in the selected working directory and provide the configured prompt to that process.

#### Scenario: Agent exits successfully

- **WHEN** the configured command exits with status zero before the timeout
- **THEN** the runner MUST return a successful structured result containing the exit status

#### Scenario: Agent exits with failure

- **WHEN** the configured command exits with a non-zero status
- **THEN** the runner MUST return a failed structured result containing the exit status and bounded diagnostic output

### Requirement: Enforce process timeout

The system MUST require a positive timeout for every agent invocation and MUST terminate an invocation that exceeds it.

#### Scenario: Invocation exceeds timeout

- **WHEN** the agent process runs longer than the configured timeout
- **THEN** the runner MUST terminate it and return a timeout classification

### Requirement: Preserve configured process context

The system MUST pass the configured working directory, environment additions, and prompt to the agent without unsafe argument rewriting.

#### Scenario: Prompt contains shell metacharacters

- **WHEN** the prompt contains quotes, dollar signs, or shell metacharacters
- **THEN** the runner MUST deliver the prompt as data and MUST NOT interpret those characters as shell syntax

### Requirement: Support dry-run

The system MUST provide a dry-run mode that displays the planned invocation and does not start an agent process.

#### Scenario: Dry-run is requested

- **WHEN** the user invokes the runner with dry-run enabled
- **THEN** the runner MUST return a dry-run result without modifying the workspace or starting the configured command
