# Design: Stream progress with explicit timing

## Explore & Reuse

- Reuse the existing subprocess runner, timeout handling, `RunResult`, loop
  stop reasons, and local verification diagnostic logs.
- Keep subprocess execution argument-list based and preserve the configured
  working directory and environment behavior.
- Add presentation callbacks or an equivalent output sink at the runner/CLI
  boundary; the loop engine must continue to return structured evidence for
  automation.
- Reuse the existing human formatter and add one duration formatter shared by
  agent, verification, heartbeat, and timeout messages.

## Behavior

While a subprocess is running, the human CLI receives line-oriented output
tagged with its component and emits a heartbeat at a bounded interval when no
new output arrives. The output is streamed for human commands but is not mixed
into machine-readable JSON. JSON continues to contain structured results, with
diagnostic paths and bounded captured streams.

Elapsed time uses one explicit format everywhere: durations below one minute
are written as `Ns` (for example, `42s`); longer durations are written as `Nm
Ns` (for example, `1m 12s`). Zero is `0s`. No human-facing duration may be a
bare number, a unitless `mm:ss`, or an ambiguous label.

When a timeout occurs, the CLI prints the component, the configured timeout in
the explicit duration format, the last bounded output if available, and the
diagnostic log path before the resume instruction. Ctrl-C returns a structured
interrupted result, leaves task and handoff files untouched by the supervisor,
and skips archive and commit hooks.

## Error handling and safety

Streaming must not disable output capture, timeout enforcement, command
argument isolation, or output bounds. Partial output received before timeout
or interruption is retained in the diagnostic log. Broken pipes or a closed
human output stream must not terminate the child without applying normal
cleanup and result classification. JSON output must remain valid JSON and must
not contain progress lines on stdout.

## Verification

Add tests for duration formatting at zero, under one minute, and over one
minute; streaming and idle heartbeat behavior; timeout output with a log path;
Ctrl-C state preservation and hook suppression; bounded output; and clean JSON
output. Run focused tests, the full suite, lint/compile checks, and strict
OpenSpec validation.
