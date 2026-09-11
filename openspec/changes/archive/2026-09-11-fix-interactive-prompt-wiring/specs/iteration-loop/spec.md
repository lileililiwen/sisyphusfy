# iteration-loop Specification

## ADDED Requirements

### Requirement: Interactive prompt works without caller setup

When `interactive` is true, the loop SHALL prompt via a built-in terminal reader unless the caller injected a custom `prompt_user`, and the human and low-level CLIs SHALL forward the interactive setting so `--interactive` reaches the prompt path.

#### Scenario: Default prompt fires

- **WHEN** a run is blocked with `interactive=True` and no explicit `prompt_user`
- **THEN** the system MUST present the blocker on the terminal and capture the decision instead of stopping silently

#### Scenario: Empty input denies visibly

- **WHEN** the operator submits empty input at the blocked prompt
- **THEN** the system MUST treat it as a denial and report that the empty input caused the denial

### Requirement: Blocker extraction honors configured markers

The system SHALL extract blocker lines using the same configured `blocked_markers` that triggered the blocked classification, falling back to the default marker set only when no custom markers are configured.

#### Scenario: Custom marker extraction

- **WHEN** a run is blocked by a custom marker
- **THEN** the system MUST present the custom marker lines rather than the full-output fallback
