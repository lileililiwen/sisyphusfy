# Context budget Specification

## Purpose
Sisyphusfy must keep its "fresh session" claim measurable. Every agent
invocation is bounded by a documented estimate and a configurable
budget, the handoff recovery contract is bounded, and the result
exposes the telemetry so operators can see what was sent and what was
truncated. The core never fabricates billing totals; adapter-supplied
exact usage is labelled as such and recorded alongside the estimate.

## Requirements

### Requirement: Measure context estimates

Each agent invocation MUST expose a documented provider-neutral estimate of
prompt/recovery input size and MUST distinguish estimates from adapter-provided
exact usage.

#### Scenario: Fresh iteration starts

- **WHEN** the loop builds an agent prompt from the task and handoff contract
- **THEN** the result MUST record the estimated context size and its measurement method

### Requirement: Enforce configurable context budgets

The loop MUST support a configurable context budget with an explicit over-budget
policy that prevents an unbounded prompt from being sent.

#### Scenario: Prompt exceeds the configured budget

- **WHEN** the rendered prompt and selected recovery material exceed the budget
- **THEN** Sisyphusfy MUST either apply the documented bounded reduction policy or stop before agent execution with an actionable result

### Requirement: Keep handoff recovery bounded

The handoff contract MUST support bounded sections for completed work, blockers,
next action, relevant files, and verification state.

#### Scenario: Handoff grows beyond its limit

- **WHEN** compaction is enabled and the handoff exceeds its configured bound
- **THEN** only the configured handoff representation MAY be compacted, and the result MUST report that compaction occurred

### Requirement: Do not replay conversation transcripts

Fresh iterations and fallback attempts MUST NOT include prior conversation
transcripts or continuation/session identifiers unless explicitly configured.

#### Scenario: Fallback starts after provider failure

- **WHEN** the next model is invoked
- **THEN** it MUST receive bounded workspace recovery context rather than the previous chat transcript

### Requirement: Expose context telemetry

Human and JSON status MUST expose context budget, estimates, truncation/compaction,
and exact usage when an adapter supplies it.

#### Scenario: Operator checks a long run

- **WHEN** the operator requests status after multiple iterations
- **THEN** the output MUST show cumulative estimated usage and any budget events without claiming unverified billing totals
