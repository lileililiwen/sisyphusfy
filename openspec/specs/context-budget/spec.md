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

### Requirement: Budget enforcement on every invocation

Every agent invocation in a run, including interactive blocked-resolution re-runs, SHALL pass through `apply_budget_to_prompt` and `telemetry.record`. A `reject` event on a re-run SHALL stop the run with `context_budget_exceeded` without invoking the agent.

#### Scenario: Re-run over budget is rejected

- **WHEN** an approved continuation prompt exceeds a `reject` budget
- **THEN** the system MUST stop with `context_budget_exceeded`, record the `rejected` event, and MUST NOT invoke the agent

#### Scenario: Telemetry counts re-runs

- **WHEN** a run contains blocked-resolution re-runs
- **THEN** telemetry totals MUST include every invocation and every `RunRecord` MUST carry its `ContextEstimate`

### Requirement: Automatic handoff compaction

When `compact_handoff` is set, the loop SHALL compact the handoff file with `HandoffCompactor` before rendering each iteration's prompt and SHALL record the before/after counts on telemetry. The compactor MUST rewrite only the configured handoff file.

#### Scenario: Compaction bounds growth

- **WHEN** `compact_handoff` is enabled and the handoff exceeds section bounds
- **THEN** the system MUST clamp it with markers before rendering the prompt and report the counts

### Requirement: Handoff-first truncation

Under the `truncate` policy, the system SHALL shrink handoff recovery content before instructions, truncating the whole body only if the budget is still exceeded, and SHALL always leave the truncation marker.

#### Scenario: Instructions survive truncation

- **WHEN** a prompt exceeds a `truncate` budget mostly due to handoff recovery
- **THEN** the truncated prompt MUST retain the instruction body and MUST carry the marker
