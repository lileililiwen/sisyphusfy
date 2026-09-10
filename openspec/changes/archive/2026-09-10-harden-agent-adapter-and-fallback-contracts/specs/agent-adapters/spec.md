# Agent adapter and fallback contracts Specification

## ADDED Requirements

### Requirement: Classify failures from both output streams

The fallback classifier MUST consider bounded combined stdout and stderr when
identifying retryable provider or process failures.

#### Scenario: Provider error is printed on stdout

- **WHEN** an agent exits non-zero and writes a quota or overload marker only to stdout
- **THEN** the configured fallback chain MUST classify it as retryable and try the next supported model

### Requirement: Do not duplicate generic command arguments

The generic adapter MUST execute each configured command argument exactly once.

#### Scenario: Generic command already contains arguments

- **WHEN** a generic adapter is configured with `agent --flag value`
- **THEN** the resulting invocation MUST contain `agent --flag value` once, without duplicated arguments

### Requirement: Fallback attempts are fresh

Each fallback attempt MUST construct a fresh command with the selected model and
MUST NOT retain a previous model option or conversation/session identifier.

#### Scenario: Fallback advances models

- **WHEN** model A fails retryably and model B is selected
- **THEN** the second command MUST contain model B exactly once and no continuation identifier from model A

### Requirement: Task failures do not rotate models

The fallback chain MUST stop on a non-retryable task-level failure.

#### Scenario: Agent reports a task error

- **WHEN** an agent exits non-zero without a retryable provider/process classification
- **THEN** the loop MUST return the failed result without invoking the next model
