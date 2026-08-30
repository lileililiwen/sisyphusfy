# Agent Adapter Specification

## ADDED Requirements

### Requirement: Select a configured agent adapter

The system MUST select an agent adapter by configuration and MUST reject unknown adapters before starting a process.

#### Scenario: Known adapter

- **WHEN** the configured adapter is registered
- **THEN** the system MUST build its command using the configured working directory and prompt

#### Scenario: Unknown adapter

- **WHEN** no adapter matches the configured name
- **THEN** the system MUST return a configuration error without starting a process

### Requirement: Use an ordered model fallback chain

The system MUST try configured models in order only after a retryable provider or process failure.

#### Scenario: First model is exhausted

- **WHEN** the first model returns a configured retryable quota/provider failure
- **THEN** the system MUST start a fresh invocation with the next model and preserve workspace state

#### Scenario: Model chain is exhausted

- **WHEN** every configured model has a retryable failure
- **THEN** the system MUST stop with an exhausted-models result

### Requirement: Avoid conversation continuation

The system MUST not pass a previous session identifier when starting a fallback attempt.

#### Scenario: Fallback starts

- **WHEN** a fallback model is selected
- **THEN** the adapter MUST create an independent invocation that reads workspace state instead of restoring conversation history
