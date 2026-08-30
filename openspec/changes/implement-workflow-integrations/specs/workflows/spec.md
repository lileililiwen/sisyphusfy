# Workflow Integration Specification

## ADDED Requirements

### Requirement: Support configurable task-state strategies

The system MUST support at least Markdown checklist, JSON predicate, and external-command completion strategies without requiring a project layout.

#### Scenario: Markdown checklist

- **WHEN** a configured Markdown task file contains unchecked items
- **THEN** the strategy MUST report incomplete work

#### Scenario: JSON predicate

- **WHEN** a configured JSON predicate evaluates true
- **THEN** the strategy MUST report completion

#### Scenario: External completion command

- **WHEN** the configured completion command exits zero
- **THEN** the strategy MUST report completion without inspecting source files

### Requirement: Support an OpenSpec workflow adapter

The system MUST support an OpenSpec change by accepting its change name, task path, and validation command as configuration.

#### Scenario: OpenSpec change is incomplete

- **WHEN** the change task file has unchecked tasks
- **THEN** the adapter MUST report incomplete work

#### Scenario: OpenSpec validation fails

- **WHEN** the configured OpenSpec validation command fails
- **THEN** the workflow MUST stop with a verification failure

### Requirement: Keep handoff context bounded

The system MUST provide a configurable concise handoff path and MUST NOT append agent transcripts to it.

#### Scenario: Iteration completes

- **WHEN** an agent finishes an iteration
- **THEN** the next prompt MUST reference the handoff path and task path without embedding the previous conversation
