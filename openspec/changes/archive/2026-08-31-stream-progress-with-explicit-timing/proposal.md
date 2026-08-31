# Proposal: Stream progress with explicit timing

## Why

Sisyphusfy currently buffers subprocess output until the agent or verification
command exits. During a long build or test run, the user sees no progress and
cannot tell whether the process is active, stalled, or waiting. Existing
elapsed-time output also needs an explicit unit so a value such as `42` cannot
be misread as minutes.

## What changes

- Stream safe agent and verification progress while each subprocess runs.
- Emit periodic heartbeat messages when a subprocess has produced no output.
- Label progress by component (`agent` or `verify`) and include elapsed time.
- Format elapsed time explicitly as `42s` or `1m 12s`; never print a bare
  number or unitless clock value.
- Report timeout limits using the same unambiguous format and immediately show
  the diagnostic log path.
- Handle Ctrl-C as an explicit interrupted stop that preserves durable state
  and does not invoke archive or commit hooks.

## Non-goals

- No shell execution or arbitrary command interpretation.
- No change to verification semantics, task completion rules, or model fallback.
- No claim that visible progress proves the subprocess is healthy.
- No default printing of secrets or unlimited output.

## Success criteria

Long-running agent and verification commands show visible progress or
heartbeats, every elapsed-time label identifies seconds, timeout output points
to diagnostics immediately, interruption preserves state safely, and focused
tests plus strict OpenSpec validation pass.
