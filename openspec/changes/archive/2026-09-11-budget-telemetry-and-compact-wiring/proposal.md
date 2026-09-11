## Why

Budget enforcement has two holes: the interactive re-run (`_augment_prompt` path) bypasses `apply_budget_to_prompt` entirely, so an approved continuation can exceed a `reject` budget the first attempt honored; and re-run prompts never record telemetry, so `ContextTelemetry` undercounts the run. Separately, `LoopConfig.compact_handoff` is a dead flag — the `HandoffCompactor` exists but nothing reads the flag and no CLI exposes it — and `truncate` policy cuts `prompt[:max_chars]` blindly, amputating instructions instead of the bulky handoff recovery section first.

## What Changes

- Route every agent invocation, including interactive re-runs, through `apply_budget_to_prompt` + `telemetry.record`; a `reject` on a re-run stops with `context_budget_exceeded` instead of invoking.
- Attach a `ContextEstimate` to every `RunRecord`, including re-run records that currently omit it.
- Wire `compact_handoff` (plus `--compact-handoff` in `run`/`resume`/`loop`): when set, compact the handoff file via `HandoffCompactor` before rendering each iteration's prompt and record the compaction outcome on telemetry.
- Make `truncate` shrink handoff recovery content before instructions: cut the handoff section first, only then the whole body, always with the marker.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `context-budget`: re-run enforcement, per-record estimates, compact wiring, handoff-first truncation.
- `iteration-loop`: every agent invocation enforces the budget and records telemetry.

## Impact

Core loop (`loop.py`), context module (`context.py`), config + human/CLI plumbing (`config.py`, `human.py`, `cli.py`). No adapter or protocol changes. This belongs in the generic core because budgeting and telemetry are engine-level, provider-neutral concerns.

## Non-goals

- No interactive `/compact` command (see `interactive-control-center`; this change is the automatic path it will reuse).
- No exact-usage parsing from provider output; estimates stay `chars/4`.
- No change to `reject` vs `truncate` policy names or JSON shapes (additive telemetry fields only).
