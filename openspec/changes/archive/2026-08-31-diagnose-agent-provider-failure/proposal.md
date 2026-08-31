# Proposal: Diagnose agent provider failures

## Why

An agent CLI such as opencode can fail with a generic server-error envelope
(`UnknownError` with a `ref` pointing at server logs the user cannot read) when
its own provider or configuration is broken — for example a default model name
that does not match a configured provider, a missing provider package, or a
corrupted config that makes opencode fall back to its hosted provider. The user
sees a cryptic `UnknownError`/`err_*` and naturally blames sisyphusfy, because
nothing tells them the failure is in their agent CLI, not the supervisor.

Because sisyphusfy is open source, every new user with a misconfigured agent CLI
hits the same dead-end. Sisyphusfy currently stops the loop and prints the
envelope, but the message points at "server logs" and looks like an internal
failure. The supervisor should make the real cause self-explanatory.

## What changes

- Add an agent-specific diagnostic hint to the structured agent error. Each
  adapter knows how to diagnose its own CLI (opencode: `opencode run 'hi'
  --print-logs --log-level DEBUG`), so the hint stays agent-agnostic.
- When the recovered error indicates a provider/config problem (a generic server
  error such as `UnknownError`, or a message about server logs), sisyphusfy
  annotates it with the hint in both the human report and the JSON result.
- A genuine, specific agent error (not a generic server error) gets no hint, so
  the real error stays prominent.
- Document the failure class and its diagnosis in a troubleshooting doc.

## Non-goals

- No auto-installation of agent-CLI provider packages or any mutation of the
  agent CLI's files. That is the agent CLI's responsibility and would break
  sisyphusfy's agent-agnostic boundary.
- No change to how the agent command is executed or to the stop-reason logic.
- No change to which errors are retryable; the hint is presentation only.

## Success criteria

A provider-side agent failure prints a clear message that the failure is in the
agent CLI/provider (not sisyphusfy) and shows the exact diagnostic command for
that adapter. A specific agent error does not get the hint. Focused tests, the
full suite, lint/compile checks, and strict OpenSpec validation must pass.
