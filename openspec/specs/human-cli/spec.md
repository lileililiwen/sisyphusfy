# human-cli Specification

## Purpose
Provide human-friendly high-level CLI commands (init, run, resume, status, doctor) that abstract the low-level loop configuration for common workflows, with automatic project discovery, configuration precedence, and clear progress output.
## Requirements
### Requirement: Provide a short common workflow

The CLI MUST provide a high-level command that can run a configured change without requiring users to provide internal task, adapter, prompt, or workflow flags for the common case.

#### Scenario: Run an OpenSpec change

- **WHEN** the user runs `sisyphusfy run <change>` in a project containing the named OpenSpec change
- **THEN** the CLI MUST discover its task state, use configured defaults, and start the durable loop

#### Scenario: Resume from durable state

- **WHEN** the user runs `sisyphusfy resume`
- **THEN** the CLI MUST continue from task and handoff files without restoring an old agent conversation

### Requirement: Support initialization and diagnostics

The CLI MUST provide `init`, `status`, and `doctor` commands with safe, understandable behavior.

#### Scenario: Initialize a project

- **WHEN** the user runs `sisyphusfy init`
- **THEN** the CLI MUST create or explain a project-local configuration without overwriting existing user configuration silently

#### Scenario: Diagnose a project

- **WHEN** the user runs `sisyphusfy doctor`
- **THEN** the CLI MUST report missing agents, models/configuration, state files, and verification prerequisites with actionable messages

### Requirement: Use discoverable configuration

The CLI MUST support project-local configuration, optional user defaults, and command-line overrides with a documented precedence order.

#### Scenario: Project override

- **WHEN** user defaults and project configuration specify different models
- **THEN** the project configuration MUST take precedence unless a command-line override is supplied

#### Scenario: No configuration file

- **WHEN** the user runs a high-level command without a configuration file
- **THEN** the CLI MUST use safe documented defaults or report exactly which input is required

### Requirement: Present useful human output

The CLI MUST show the project, change, agent, model chain, iteration progress, fallback events, blockers, and next action in concise human-readable output.

#### Scenario: Model fallback

- **WHEN** a retryable provider failure exhausts the current model
- **THEN** the CLI MUST state the fallback model and continue with preserved workspace state

#### Scenario: Blocked session

- **WHEN** an agent requests permission or an unresolved choice
- **THEN** the CLI MUST stop, explain the blocker, identify preserved state files, and show the resume command

### Requirement: Preserve explicit safety gates

The high-level CLI MUST keep dry-run, archive, and commit explicit, and MUST preserve JSON output for automation.

#### Scenario: Normal completion

- **WHEN** a run completes without `--archive` or `--commit`
- **THEN** the CLI MUST not invoke archive or commit hooks

#### Scenario: Dry-run

- **WHEN** dry-run is enabled
- **THEN** the CLI MUST inspect and display the planned actions without invoking agents, verification, or hooks

