# iteration-loop Specification Deltas

## MODIFIED Requirements

### Requirement: Verify and classify outcomes

The system MUST run the configured verification command only after an agent
iteration exits zero and MUST expose distinct complete, failed, agent-failed,
timeout, blocked, and verification-failure results.

#### Scenario: Verification succeeds and work is complete

- **WHEN** verification succeeds and state reports completion
- **THEN** the system MUST stop with a complete result

#### Scenario: Verification fails

- **WHEN** the verification command exits non-zero
- **THEN** the system MUST stop with a verification-failure result

#### Scenario: Agent is blocked

- **WHEN** the agent reports a permission request or unresolved choice
- **THEN** the system MUST record the blocker and stop without guessing an answer

#### Scenario: Agent fails before verification

- **WHEN** an agent process exits with a non-zero status
- **THEN** the system MUST NOT run the verification command and MUST NOT invoke
  completion hooks for that iteration

## ADDED Requirements

### Requirement: Stop when an agent run fails

The system MUST stop the loop in the same iteration when an agent process exits
with a non-zero status, whether or not a model chain is configured. The
command-not-found, interrupted, timeout, and blocked classifications MUST keep
priority over the agent-failed classification, and the stop MUST happen before
verification and before completion hooks.

#### Scenario: Agent fails with no model chain

- **WHEN** no model chain is configured and the agent exits non-zero
- **THEN** the system MUST stop with an `agent_failed` result in that iteration

#### Scenario: Blocked output wins over agent failure

- **WHEN** the agent exits non-zero and its output contains a configured blocked
  marker
- **THEN** the system MUST stop with a `blocked` result instead of `agent_failed`

#### Scenario: Timeout is not reclassified

- **WHEN** an agent run reaches its timeout, with or without a model chain
- **THEN** the system MUST stop with a `timeout` result even though the runner
  reports a non-zero exit status

#### Scenario: Non-retryable failure with a model chain

- **WHEN** a configured model fails with a non-retryable classification
- **THEN** the system MUST stop with an `agent_failed` result and MUST NOT try
  the remaining models
