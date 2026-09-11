# iteration-loop Specification

## Purpose
Bounded fresh iterations with durable state persistence and verification of
iterations that exit zero. A failed agent run stops the loop. A blocked marker
either stops with a `blocked` result (non-interactive) or, when a terminal is
available, pauses for an explicit operator decision and re-runs the agent in the
same iteration with the answer folded into the prompt; denial or an unresolvable
blocker still stops with `blocked`.
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

### Requirement: Resolve blocked runs interactively when a terminal is available

When an agent run reports a permission request or unresolved choice (a configured
blocked marker) and a terminal is available, the system MUST pause and present the
blocker to the user, capture an explicit decision (approve, deny, or a free-text
answer), and re-run the agent in the same iteration with the answer folded into the
prompt so the loop continues. The system MUST NOT auto-approve a privileged or
destructive blocker; denial or an unresolvable blocker MUST stop the iteration with
a `blocked` result, with verification and hooks still not run. The system MUST bound
the number of interactive re-prompts per iteration so an unresolvable blocker cannot
loop forever. In a non-interactive context (piped input, CI, `--json`, or
`interactive: false`) the system MUST keep the existing behavior: stop with
`blocked`, report the blocker, and print the resume command, and MUST NOT block
waiting for input.

#### Scenario: Interactive approve continues the loop

- **WHEN** a run is blocked, a terminal is available, and the user approves (or supplies an answer)
- **THEN** the system MUST re-run the agent in the same iteration with the answer and continue past the blocker

#### Scenario: Interactive deny stops the loop

- **WHEN** a run is blocked and the user denies
- **THEN** the system MUST stop the iteration with a `blocked` result and MUST NOT re-run the agent

#### Scenario: Non-interactive still stops and reports

- **WHEN** a run is blocked in a non-interactive context
- **THEN** the system MUST stop with `blocked`, report the blocker, and print the resume command, and MUST NOT prompt for input

#### Scenario: Unresolvable blocker is bounded

- **WHEN** a blocked run is re-prompted up to the configured cap without resolving
- **THEN** the system MUST stop the iteration with `blocked` rather than re-running indefinitely

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

### Requirement: Loop delegates model flags to adapters

The iteration loop SHALL NOT perform `--model`/`-m` argument surgery on adapter-built commands; it SHALL pass the active model to the adapter and invoke the returned command unchanged.

#### Scenario: Adapter-built command passes through

- **WHEN** an adapter builds a command for a fallback model
- **THEN** the loop MUST invoke that command without rewriting its model arguments

