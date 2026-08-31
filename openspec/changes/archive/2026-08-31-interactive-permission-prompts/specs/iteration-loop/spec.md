# iteration-loop Specification

## ADDED Requirements

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
