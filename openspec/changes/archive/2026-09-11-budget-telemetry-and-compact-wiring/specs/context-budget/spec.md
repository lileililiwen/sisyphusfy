# context-budget Specification

## ADDED Requirements

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
