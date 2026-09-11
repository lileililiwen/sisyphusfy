## Why

Supervising a long loop today is hands-off until it stops: there is no way to pause mid-run with ESC, and the blocked prompt only understands approve/deny, so routine needs — switching models after a quota failure, compacting a bloated handoff — require killing the run and restarting by hand. Agent CLIs already offer `/models`- and `/compact`-style on-the-fly commands; the supervisor should match that ergonomics at its own layer (loop control, not agent internals).

## What Changes

- ESC pauses the loop at the next safe point (between agent invocations and inside the blocked prompt; v1 does not suspend a running subprocess) and offers resume / stop / step-once.
- The blocked prompt becomes a small REPL accepting slash commands alongside approve/deny:
  - `/models [name]` — list the configured chain (with skip/active marks) or switch the active model for subsequent invocations.
  - `/compact` — compact the handoff file now via `HandoffCompactor` and report before/after counts.
  - `/help` — list commands; `/resume`, `/stop` — continue or end as `blocked`.
- Unknown `/` input prints help and re-prompts; it never reaches the agent as an answer.
- All control actions are recorded on `LoopResult` telemetry (pause count, model switches, compactions).

## Capabilities

### New Capabilities

- `interactive-control`: ESC pause semantics and the blocked-prompt slash-command REPL.

### Modified Capabilities

(none — additive; `iteration-loop` and `human-cli` gain no changed requirements, only a new control surface.)

## Impact

Core loop (`loop.py` prompt loop), terminal input handling (new small `control.py`, POSIX `termios`/`tty` with Windows fallback to Ctrl-C-only), human CLI output. No adapter, protocol, or JSON-shape changes (additive telemetry fields only). This is generic core: key handling and loop control are identical for every adapter.

## Non-goals

- No mid-subprocess SIGSTOP/SIGCONT suspension in v1; ESC during a running agent sets a pending-pause honored at the next boundary. True process-group suspension is a follow-up.
- No piping answers into a live agent process; the fresh-session model is unchanged.
- No provider model catalog; `/models` operates on the configured chain plus adapter `supports_model` marks.
- No new behavior under `--json` or piped input: non-interactive runs ignore keys and slash handling entirely.
