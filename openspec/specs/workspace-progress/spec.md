# Workspace progress Specification

## Purpose
The loop must recognise real progress without being fooled by ordinary
prose, silently-broken configuration, or a checklist variant it does not
understand. Workspace changes (when opted in) count as progress, blocked
detection is explicit, configured paths stay inside the project, checklist
parsing is consistent, and malformed configuration surfaces as a
structured error.

## Requirements

### Requirement: Report configurable workspace progress

The loop MUST support an opt-in workspace-change snapshot in addition to task
and handoff snapshots, without requiring Git for the default workflow.

#### Scenario: Agent changes source but not checklist

- **WHEN** the agent exits successfully and changes an opted-in workspace file
- **THEN** the loop MUST report workspace progress instead of immediately returning unchanged_state

### Requirement: Avoid broad blocker false positives

Blocked detection MUST use explicit configured marker rules and MUST NOT treat
arbitrary occurrences of words such as “permission” in normal output as a
blocker unless the configured rule matches.

#### Scenario: Test output mentions permissions

- **WHEN** successful agent output contains ordinary prose about file permissions
- **THEN** the loop MUST NOT enter blocked handling unless an explicit blocker marker is present

### Requirement: Enforce project path boundaries

Task, handoff, and workflow paths MUST resolve inside the selected project
directory by default, and an escape MUST produce a structured configuration
error before command execution.

#### Scenario: Relative path escapes the project

- **WHEN** a configured path resolves through `..` outside the selected project
- **THEN** the run MUST stop before invoking the agent and identify the escaping path

### Requirement: Parse checklist variants consistently

Markdown and OpenSpec checklist adapters MUST recognize supported uppercase and
lowercase checked markers consistently.

#### Scenario: Task uses uppercase checked marker

- **WHEN** all task items use `- [X]`
- **THEN** the adapter MUST report the task as complete

### Requirement: Surface malformed configuration

Invalid project or user configuration MUST produce a structured error naming the
source and parse failure instead of silently using unrelated defaults.

#### Scenario: Project TOML is malformed

- **WHEN** `.sisyphusfy.toml` cannot be parsed
- **THEN** CLI human and JSON modes MUST report configuration failure and MUST NOT start an agent with silent defaults
