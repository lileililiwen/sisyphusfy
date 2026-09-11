## Why

Model handling has three sharp edges: the loop's `--model` rewrite (`cmd[i+1] = model`) crashes with `IndexError` when a command ends in `--model`; the model is injected twice (once by the adapter's `build_command`, once by the loop); and `GenericCommandAdapter` ignores models while the loop blindly appends `--model X` to arbitrary user commands. Separately, `try_fallback` skips `supports_model==False` models without recording them, so an all-skipped chain raises `ModelChainExhausted(last_result=None)` and the loop hands `None` into agent-stop evidence handling.

## What Changes

- Single model-injection owner: the adapter builds the final command for a given model; the loop stops rewriting `--model` flags (guard the legacy path if kept: never index past the end).
- `GenericCommandAdapter` only appends `--model` when its wrapped command declares model support (opt-in marker); otherwise it passes the model via `AGENT_MODEL` env only (already done by `_run_iteration`).
- `try_fallback` records skipped models distinctly, returns the skip list in `attempts`, and raises `ModelChainExhausted` with a typed `last_result=None` that callers handle as "no attempt ran" instead of agent evidence.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-adapters`: model injection ownership and skip accounting.
- `iteration-loop`: loop stops rewriting adapter model flags; all-skipped chain stops cleanly.

## Impact

Core loop (`loop.py`), adapters (`adapters.py`), fallback tests. No protocol method additions; `AgentAdapter` contract unchanged. This spans core + adapters because the bug is the duplicated responsibility between them.

## Non-goals

- No interactive `/models` switching (see `interactive-control-center`).
- No model catalog or validation of model names against providers.
- No change to retryable vs non-retryable classification.
