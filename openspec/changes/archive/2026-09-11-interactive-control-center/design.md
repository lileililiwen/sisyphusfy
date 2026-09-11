## Context

The supervisor owns `stdin` only indirectly today: the agent child gets `stdin=PIPE` while the blocked prompt does a blocking `readline`. There is no key listener, no command parser, and no pause state — the loop runs iteration to iteration until a stop reason fires. Long quota-bound or overnight runs need operator steering without process surgery. Constraints: must stay agent-agnostic (control the loop, never the agent CLI's internals), must never hang non-interactive runs, must keep the fresh-session contract.

## Goals / Non-Goals

**Goals:**
- ESC reliably pauses at safe points with a clear resume/stop choice.
- Operators can switch models and compact handoffs without killing the run.
- Every control action is auditable on the result.

**Non-Goals:**
- Suspending a live subprocess mid-write (v1 honors pause at boundaries only).
- A full TUI, scrolling, or mouse handling.

## Explore & Reuse

- Reuse the blocked-prompt site as the REPL host: it already runs between invocations with the blocker in context; slash parsing slots in before the approve/deny branch.
- Reuse `HandoffCompactor.compact` for `/compact` and the automatic path from `budget-telemetry-and-compact-wiring`; the REPL reports the same `before_chars`/`after_chars`.
- Reuse `model_chain` + `supports_model` for `/models` listing and switching; depends on `harden-model-flag-and-fallback` for truthful skip marks.
- Reuse `StreamProgress` stderr channel for pause notices; the prompt itself stays on stderr so `--json` stdout stays clean.
- POSIX `termios`/`tty` raw-mode reader in a daemon thread, guarded by `sys.stdin.isatty()`; Windows keeps Ctrl-C behavior (documented limitation).

## Decisions

- **Boundary pause, not SIGSTOP, for v1.** Suspending a subprocess group mid-pipe risks wedged reader threads and half-written state files. A pending-pause flag checked after each invocation and inside the REPL is race-free. Alternative (SIGSTOP/SIGCONT the group) was rejected for v1; kept as an explicit follow-up.
- **REPL inside the blocked prompt, not a global hotkey shell.** The prompt already has the operator's attention and a defined input context; a global shell would need PTY multiplexing with agent output. `/models`/`/compact` outside blocked stops arrive via the ESC pause menu (same parser).
- **Slash input never becomes agent text.** Commands are consumed by the parser; only plain-text answers fold into `_augment_prompt`. Alternative (pass `/models x` through on unknown) was rejected: leaking control syntax into task prompts corrupts runs.
- **New `control.py`, not loop inline.** Key reading, escape-sequence parsing (`\x1b` vs `\x1b[` arrows), and command dispatch are independently testable without subprocesses.

## Risks / Trade-offs

- [Risk] ESC arrow-key sequences (`\x1b[A`) misread as pause → Mitigation: parse full CSI sequences; lone `ESC` (with short read timeout) is the pause key.
- [Risk] Raw-mode terminal left unconfigured on crash → Mitigation: context-manager restores `termios` attrs in `finally`; tests use pipes, never raw mode.
- [Risk] `/models` switch to an unsupported model → Mitigation: check `supports_model` first and refuse with the skip reason; record refused attempts.
- [Risk] Overlap with the three sibling changes → Mitigation: land order `fix-interactive-prompt-wiring` → `harden-model-flag-and-fallback` → `budget-telemetry-and-compact-wiring` → this change; each validates independently.

## Migration Plan

Additive only. No config migration; new keys/flags default off except the REPL enriching the already-interactive prompt. Rollback is a revert with no state cleanup.
