# agent-adapters Specification

## ADDED Requirements

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
