## Why

The interactive blocked-resolution path shipped in `2026-08-31-interactive-permission-prompts` never fires in production: `LoopConfig.prompt_user` defaults to `None`, neither `human._execute_loop` nor `cli._run_loop` sets it, and the loop guard requires `interactive and prompt_user is not None`. Separately, `_extract_blocker` matches against the global `BLOCKED_MARKERS` while `_is_blocked` honors `config.blocked_markers`, so custom markers stop the loop but the operator is shown a fallback dump instead of the marker lines.

## What Changes

- Default `LoopConfig.prompt_user` to `_read_terminal_answer` so the loop is self-sufficient; keep it injectable for tests.
- Wire `interactive` + `prompt_user` through `human._execute_loop` and `cli._run_loop` (both currently drop `prompt_user`).
- Thread configured `blocked_markers` into `_extract_blocker(result, markers)`; fall back to global markers when empty.
- Treat empty input explicitly: keep deny-on-empty but print the decision so Enter no longer silently aborts.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `iteration-loop`: interactive prompt defaults and marker-consistent blocker extraction.

## Impact

Core loop (`loop.py`), human CLI (`human.py`), low-level CLI (`cli.py`). No adapter, protocol, or JSON-shape changes. This belongs in the generic core because blocked detection and prompting are engine behavior shared by all adapters.

## Non-goals

- No ESC handling or slash commands (see `interactive-control-center`).
- No change to blocked-marker matching semantics or the non-interactive contract.
- No mid-run pause; prompting still happens between agent invocations only.
