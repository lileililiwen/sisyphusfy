# agent-adapters Specification Deltas

## MODIFIED Requirements

### Requirement: Use an ordered model fallback chain

The system MUST try configured models in order only after a retryable provider
or process failure, and MUST stop the iteration instead when a failure is
classified non-retryable.

#### Scenario: First model is exhausted

- **WHEN** the first model returns a configured retryable quota/provider failure
- **THEN** the system MUST start a fresh invocation with the next model and
  preserve workspace state

#### Scenario: Model chain is exhausted

- **WHEN** every configured model has a retryable failure
- **THEN** the system MUST stop with an exhausted-models result

#### Scenario: Non-retryable failure ends the iteration

- **WHEN** a model fails with a non-retryable classification
- **THEN** the system MUST stop with an `agent_failed` result, MUST NOT advance
  to the next model, and MUST reserve the exhausted-models result for the case
  where every configured model failed retryably

## ADDED Requirements

### Requirement: Report a structured agent error

The `AgentAdapter` protocol MUST include `parse_error(output)`, and every
built-in adapter MUST implement it. `parse_error` MUST accept the agent's
combined stdout and stderr and MUST return the recovered error name, message,
and reference, or `None` when the output carries no recognizable error. The loop
MUST call it defensively so an adapter that does not implement it, or one that
raises, degrades to no structured error instead of failing the run.

#### Scenario: Agent prints a JSON error envelope

- **WHEN** an agent's combined output contains a JSON object with a `name` and a
  `data` object carrying `message` and `ref`
- **THEN** `parse_error` MUST return those values as the error name, message, and
  reference

#### Scenario: Envelope arrives on either stream

- **WHEN** the same envelope is written to stdout instead of stderr
- **THEN** `parse_error` MUST return the same structured error

#### Scenario: No recognizable error

- **WHEN** agent output contains no JSON error object, or contains a malformed
  one
- **THEN** `parse_error` MUST return `None` and the loop MUST still stop with an
  `agent_failed` result based on the exit status
