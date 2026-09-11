## Context

`build_command(working_directory, prompt)` already receives the adapter's configured model at construction time, yet per-iteration fallback models are applied afterwards by string-surgery in `_run_iteration`. The two owners disagree: adapters that embed `--model` get their flags rewritten, and generic commands that never asked for `--model` get one appended. The fallback loop separately treats "unsupported" as "invisible", losing the audit trail. The fix consolidates command construction per model in one place.

## Goals / Non-Goals

**Goals:**
- One crash-free path from (adapter, model) to command line.
- Skipped models visible in `model_attempts` instead of vanishing.
- All-skipped chain produces a clean stop, never a `None`-evidence crash.

**Non-Goals:**
- No provider-side model validation.
- No change to which failures are retryable.

## Explore & Reuse

- Reuse the existing `AGENT_MODEL` env pass-through in `_run_iteration` as the universal model channel for commands that do not accept a flag.
- Reuse `supports_model` as the skip predicate; only the bookkeeping around it changes.
- Reuse `ModelChainExhausted.attempts` to carry skips; extend the dataclass with a `skipped` field rather than inventing a new error type.
- Keep `AdapterConfig.command` + `agent_command` resolution untouched.

## Decisions

- **Adapter owns the flag.** The adapter knows its CLI grammar; the loop only supplies the model value. Alternative (loop owns all flag logic) was rejected: every new adapter CLI would require loop changes, violating the adapter boundary.
- **Opt-in flag for generic commands.** Default off: appending unknown flags to user commands breaks them. Commands that accept `--model` declare it; others get env-only. Alternative (always append, current behavior) was rejected as the reported breakage.
- **Skips stay in the trail.** `attempts` records every model considered with a `skipped` subset, so `LoopResult.model_attempts` remains the full audit trail. Alternative (raise a distinct `NoSupportedModel` error) was rejected: callers already handle `ModelChainExhausted`.

## Risks / Trade-offs

- [Risk] Generic commands that relied on the appended `--model` stop receiving it → Mitigation: opt-in marker documented in `docs/adapters.md`; env `AGENT_MODEL` still delivered.
- [Risk] `model_attempts` contents change shape for skipped models → Mitigation: additive `skipped` field; existing assertions on attempted models keep passing.
