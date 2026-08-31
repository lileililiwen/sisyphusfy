# agent-adapters Specification

## Purpose
Agent adapter selection, ordered model fallback chain for retryable failures,
structured agent error reporting, and no conversation continuation.
## Requirements
### Requirement: Select a configured agent adapter

The system MUST select an agent adapter by configuration and MUST reject unknown adapters before starting a process.

#### Scenario: Known adapter

- **WHEN** the configured adapter is registered
- **THEN** the system MUST build its command using the configured working directory and prompt

#### Scenario: Unknown adapter

- **WHEN** no adapter matches the configured name
- **THEN** the system MUST return a configuration error without starting a process

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

### Requirement: Avoid conversation continuation

The system MUST not pass a previous session identifier when starting a fallback attempt.

#### Scenario: Fallback starts

- **WHEN** a fallback model is selected
- **THEN** the adapter MUST create an independent invocation that reads workspace state instead of restoring conversation history

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

### Requirement: Report provider-side agent errors with a diagnostic hint

When an agent run fails and the recovered error indicates a provider or
configuration problem at the agent CLI (for example an opencode `UnknownError`
envelope), the system MUST annotate the error with an agent-specific diagnostic
hint instead of leaving the user with an opaque server error and a reference to
logs they cannot read. The hint MUST state that the failure is in the agent
CLI/provider, not in sisyphusfy, and MUST give the exact command to diagnose it.
Detection MUST be generic (based on the error name or message), and the
agent-specific command MUST come from the adapter so sisyphusfy stays
agent-agnostic.

#### Scenario: opencode UnknownError

- **WHEN** the agent CLI returns an `UnknownError` envelope and stops the loop
- **THEN** sisyphusfy MUST report that this is an agent-CLI/provider issue, not a sisyphusfy failure, and show the adapter's diagnostic command (for opencode: `opencode run 'hi' --print-logs --log-level DEBUG`)

#### Scenario: Other agent CLIs

- **WHEN** a different adapter's agent fails with a provider-side error
- **THEN** sisyphusfy MUST show that adapter's diagnostic command

#### Scenario: Genuine agent error

- **WHEN** the agent fails with a specific, actionable error that is not a generic server error
- **THEN** sisyphusfy MUST NOT add a provider-config hint, so the real error stays prominent

