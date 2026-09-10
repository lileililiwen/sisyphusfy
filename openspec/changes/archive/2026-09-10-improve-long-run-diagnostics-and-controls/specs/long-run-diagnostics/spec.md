# Long-run diagnostics Specification

## ADDED Requirements

### Requirement: Label diagnostic components

Saved diagnostic evidence MUST identify its component and MUST use distinct
agent, verification, workflow, and hook naming where streams could otherwise be
confused.

#### Scenario: Agent fails before verification

- **WHEN** an agent exits non-zero
- **THEN** the reported diagnostic path MUST be identifiable as agent evidence and MUST NOT be labelled as verification-only

### Requirement: Configure verification timeout at high level

The `run` and `resume` commands MUST accept a verification-timeout override and
show the effective value in dry-run and structured output.

#### Scenario: Project verification exceeds the default

- **WHEN** the operator supplies `--verification-timeout 600`
- **THEN** the verifier MUST receive a 600-second limit and the planned/effective configuration MUST expose that value

### Requirement: Inspect diagnostics without rerunning work

An explicit verbose diagnostic inspection MUST read saved evidence without
starting another agent iteration or verification process.

#### Scenario: Resume diagnostics are requested

- **WHEN** the operator requests verbose inspection of a prior result
- **THEN** Sisyphusfy MUST display the saved diagnostic or a clear missing-log state without rerunning the loop

### Requirement: Keep normal output concise and actionable

Human output MUST summarize component, status, duration, next action, and
diagnostic location while reserving full streams for explicit inspection.

#### Scenario: Verification fails

- **WHEN** verification exits non-zero
- **THEN** normal output MUST show the failure status, elapsed duration, log path, and a resume/inspection action

### Requirement: Preserve machine-readable evidence

JSON output MUST include stable component, timeout, duration, exit status, and
diagnostic path fields without embedding unbounded streams.

#### Scenario: Automation consumes a failed run

- **WHEN** a run returns a failed JSON result
- **THEN** an automation client MUST be able to identify the failed component and retrieve bounded evidence without parsing human text
