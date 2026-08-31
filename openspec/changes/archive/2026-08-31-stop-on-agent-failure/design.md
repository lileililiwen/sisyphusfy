# Design: Stop on agent failure

## Explore & Reuse

- Reuse the existing subprocess runner, `RunResult` classification, loop stop
  reasons, and the local diagnostic log writer. Nothing new is added at the
  process boundary; the bug is entirely in how the loop reads the result.
- Reuse `_agent_stop()` (added for timeouts and interruption) as the single way
  to stop after an agent run. It already records `VerificationEvidence` under
  the `agent` component and writes the diagnostic log, so agent failures gain
  retained evidence without a parallel path.
- Reuse `try_fallback()` as the only owner of fallback policy. It already
  returns on exit 0 or a non-retryable classification and raises
  `ModelChainExhausted` when every model failed retryably, so the loop never
  needs to re-classify a result the chain has already judged.
- Reuse the `_print_timeout_detail()` / `_print_verifier_status()` shape for the
  agent-failure report: component and status, then bounded detail lines, then
  the diagnostics path and resume instruction.
- Do not add a second error-parsing path in the loop engine. Adapters already
  own agent-specific knowledge (`build_command`, `classify_failure`), so error
  extraction becomes a fourth protocol method and the engine stays CLI-agnostic.

## Behavior

After an agent run, the loop stops with `agent_failed` whenever the exit status
is non-zero. The check sits after the `command_not_found`, `interrupted`,
`timed_out`, and `blocked` classifications, all of which are more specific and
must keep winning, and before verification. Verification therefore runs only
after an agent iteration exits zero, which is what the `iteration-loop` spec
already required and what the `and config.model_chain` guard broke.

A blocked run stays `blocked` even when the agent also exits non-zero: the
agent asked for a decision, which is more actionable than a generic failure.
A timeout stays `timeout`: the runner reports `exit_status = -1`, so a timeout
is also a non-zero exit and must not be reclassified.

When a model chain is configured, `try_fallback` remains the sole fallback
authority. A non-retryable classification returns to the loop and stops as
`agent_failed` without trying further models; `models_exhausted` is reserved for
the case where every configured model failed retryably. That chain-exhausted
path also retains its last attempt's evidence, so `--verbose` can show why every
model failed instead of reporting that no diagnostics exist.

Agent error recovery is best-effort. The loop asks the adapter to parse the
combined stdout and stderr; the built-in adapters extract the first balanced
JSON object carrying a `name`, reading the message from `data.message` and the
reference from `data.ref`. Parsing never raises and never blocks the stop: when
no envelope is recognizable, the result still reports `agent_failed` with the
exit status and the diagnostic log path, just without `error:` and `reference:`
lines. Third-party adapters written against the three-method protocol are
called defensively, so a missing or failing parser degrades to no structured
error rather than taking the supervisor down.

## Error handling and safety

Streaming, output capture, timeout enforcement, command argument isolation, and
output bounds are untouched. A failed run writes the same bounded diagnostic log
as any other stop; environment values and prompts are still never recorded. The
default human result stays concise: it prints the failing command, exit status,
recovered message and reference, and the log path, and never dumps the raw
streams. JSON carries the structured error and bounded evidence and stays valid;
progress lines remain on stderr. Structured results are never replaced by an
agent's own claims about what it did.

## Verification

Add tests for a non-zero agent exit with and without a model chain; that the
verifier never runs after a failed agent; that blocked, timeout, interrupted,
and command-not-found keep priority; envelope parsing from either stream plus
the no-match and malformed cases; the human output block, JSON shape, and
`--verbose` agent diagnostics; and the two existing assertions that encoded the
old behavior. Run focused tests, the full suite, lint/compile checks, and strict
OpenSpec validation.
