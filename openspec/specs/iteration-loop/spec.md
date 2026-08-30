# iteration-loop Specification

## Purpose
Bounded fresh iterations with durable state persistence and verification.

## Requirements

### Requirement: Execute bounded fresh iterations

The system MUST execute at most the configured number of iterations, invoking a fresh agent process for each iteration.

#### Scenario: Work remains

- **WHEN** task state reports incomplete work and the iteration limit is not reached
- **THEN** the system MUST invoke one new agent process for the next iteration

#### Scenario: Iteration limit reached

- **WHEN** the configured maximum is reached
- **THEN** the system MUST stop with a limit classification

### Requirement: Persist and inspect durable state

The system MUST use configured task and handoff paths without assuming a language or repository layout.

#### Scenario: Agent updates state

- **WHEN** an iteration exits successfully and task or handoff content changes
- **THEN** the system MUST retain the changed workspace state for the next iteration

#### Scenario: Agent does not update state

- **WHEN** an iteration exits successfully but configured state is unchanged
- **THEN** the system MUST stop with an unchanged-state classification

### Requirement: Verify and classify outcomes

The system MUST run the configured verification command after a successful agent iteration and MUST expose distinct complete, failed, timeout, blocked, and verification-failure results.

#### Scenario: Verification succeeds and work is complete

- **WHEN** verification succeeds and state reports completion
- **THEN** the system MUST stop with a complete result

#### Scenario: Verification fails

- **WHEN** the verification command exits non-zero
- **THEN** the system MUST stop with a verification-failure result

#### Scenario: Agent is blocked

- **WHEN** the agent reports a permission request or unresolved choice
- **THEN** the system MUST record the blocker and stop without guessing an answer
