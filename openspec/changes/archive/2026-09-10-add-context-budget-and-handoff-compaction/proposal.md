# Proposal: Add context budgets and handoff compaction

## Why

Fresh sessions avoid replaying chat history, but Sisyphusfy does not measure
prompt size, cap handoff growth, or provide a compact recovery contract. Agents
can still rediscover large repositories or receive increasingly expensive
handoffs, so the token-saving claim is not measurable or enforceable.

## Scope

- Add provider-neutral prompt-size estimation and configurable budgets.
- Add cumulative per-run token/cost telemetry with clearly marked estimates.
- Define bounded structured handoff sections and optional compaction.
- Expose context budget status in human and JSON output.

## Non-goals

- No provider-specific tokenizer in the core.
- No automatic deletion of user-owned project history.
- No conversation continuation or transcript persistence.
- No claim of exact billing without adapter-supplied usage data.

This belongs in the generic prompt/diagnostic contract; tokenizer and usage
adapters may provide optional provider-specific precision.
