## 1. Testing

- [x] 1.1 Add a test: an interactive re-run whose augmented prompt exceeds a `reject` budget stops with `context_budget_exceeded` and does not invoke the agent.
- [x] 1.2 Add a test: re-run records carry `ContextEstimate` and telemetry totals equal all invocations including re-runs.
- [x] 1.3 Add a test: `compact_handoff=True` compacts the handoff before rendering and records before/after counts.
- [x] 1.4 Add a test: `truncate` cuts handoff recovery content before instructions and keeps the truncation marker.

## 2. Unified enforcement

- [x] 2.1 Extract `_prepare_prompt` (budget + telemetry) and call it from the iteration head and the blocked re-run branch.
- [x] 2.2 Attach `ContextEstimate` to every `RunRecord` including re-runs.

## 3. Compact wiring and truncation order

- [x] 3.1 Wire `compact_handoff` through config, `human`, and `cli` (`--compact-handoff`) into per-iteration compaction.
- [x] 3.2 Reorder `truncate` to shrink handoff recovery first, whole body second.

## 4. Documentation and validation

- [x] 4.1 Document `compact_handoff`, re-run enforcement, and truncation order in `docs/configuration.md`.
- [x] 4.2 Run focused tests, the full suite, `ruff check`, `compileall`, and `openspec validate --all --strict`.
