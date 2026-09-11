## Context

`_run_loop` enforces the budget at the top of each iteration but the blocked-resolution branch calls `_run_with_model(p=augmented)` directly, skipping the two lines that keep the budget honest. The same branch appends `RunRecord`s without `context_estimate`. `compact_handoff` was added to `LoopConfig` as an opt-in without a reader, and `apply_budget_to_prompt` truncates from the tail of the composed body, which penalizes the fixed instructions that are cheapest to keep and most expensive to lose.

## Goals / Non-Goals

**Goals:**
- Zero unenforced agent invocations per run when a budget is set.
- Telemetry totals equal the sum of actual invocations.
- `compact_handoff=True` measurably bounds handoff growth across iterations.
- Truncation preserves instructions; handoff recovery absorbs the cut first.

**Non-Goals:**
- No key handling or REPL; the interactive `/compact` reuses the compactor wired here.
- No transcript replay; fresh-session composition stays as-is.

## Explore & Reuse

- Reuse `apply_budget_to_prompt` + `telemetry.record` + `estimate_text` by extracting a single `_prepare_prompt(raw, budget, telemetry)` helper called by both the iteration head and the re-run branch.
- Reuse `HandoffCompactor.compact(handoff_path)` as the per-iteration pre-step when `compact_handoff` is set; it already rewrites only the handoff file and reports before/after counts.
- Reuse `budget_event` recording (`rejected`/`truncated`) so re-run enforcement surfaces in the existing telemetry channel.
- Keep `HandoffDocument` section parsing provider-neutral; truncation order (handoff first, then body) is a core policy, not an adapter concern.

## Decisions

- **Enforce-then-record helper, not duplicated lines.** One function both call sites share; otherwise the next branch will drift again. Alternative (patch the re-run branch inline) was rejected as the pattern that caused this bug.
- **Compact before render, each iteration.** Compaction rewrites the file the prompt then reads, so later iterations benefit. Alternative (compact once at start) was rejected: handoffs regrow every iteration.
- **Handoff-first truncation.** Instructions are fixed and small; handoff recovery is variable and large. Cutting recovery first preserves task fidelity longest. Alternative (keep blind tail-cut) was rejected as instruction-amputating.
- **Reject on re-run stops, not skips.** A `reject` means the operator's approved continuation does not fit; silently dropping the answer would be worse than stopping with `context_budget_exceeded`.

## Risks / Trade-offs

- [Risk] Re-runs that previously proceeded now stop on `reject` → Mitigation: this is the documented meaning of `reject`; operators wanting leniency use `truncate`.
- [Risk] Per-iteration compaction rewrites user-visible handoff files → Mitigation: compactor only clamps sections with markers, never deletes history silently; counts recorded on telemetry.
