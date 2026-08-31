# Proposal: Stop on agent failure

## Why

When an agent process exits non-zero, Sisyphusfy currently only classifies the
failure when `model_chain` is configured. `src/sisyphusfy/loop.py` guards the
non-zero-exit branch with `and config.model_chain`, so with the default
`model_chain = []` control falls through and the configured verification
command runs against a workspace the agent never updated.

The observed run: `opencode` exited 1 with an `UnknownError` envelope carrying
`ref: err_cbece906`, and Sisyphusfy then ran `dotnet test`, printing its restore
and build output as if the iteration had produced something to verify. The
verifier output is not evidence about anything, and it hides the real failure.

This already violates the archived `iteration-loop` requirement, which says
verification runs "after a **successful** agent iteration". The loop also loses
the agent error: the message and reference are only visible in the live progress
stream and are never returned in the loop result, so automation cannot see them.

## What changes

- Add an `agent_failed` stop reason and stop the loop in the same iteration for
  any non-zero agent exit, before verification and before completion hooks.
- Run verification only after an agent iteration exits zero.
- Keep `command_not_found`, `interrupted`, `timeout`, and `blocked`
  classifications ahead of `agent_failed`.
- Map a non-retryable model-chain failure to `agent_failed`, reserving
  `models_exhausted` for the case where every configured model failed retryably.
- Extend the `AgentAdapter` protocol with `parse_error(output)` so adapters
  recover a structured error name, message, and reference from agent output;
  the built-in adapters share one JSON-envelope parser.
- Persist the recovered agent error and the failed run's bounded evidence
  (command, exit status, output metadata, diagnostic log path) in the loop
  result and JSON, and report them concisely with the resume instruction.

## Non-goals

- No interactive permission prompts for blocked runs; that is a separate change.
- No automatic retry of a failed agent iteration, and no change to model
  fallback: only retryable classifications advance the chain.
- No change to verification semantics, completion rules, or commit authorization.
- No assumption that every agent prints a machine-readable error; when no error
  can be recovered, the stop reason and diagnostics still stand on their own.
- No attempt to prove the agent was healthy from its output.

## Success criteria

A non-zero agent exit with or without a model chain stops the loop as
`agent_failed` without running the verifier; a successful agent still verifies;
an agent that prints a JSON error envelope has its message and reference shown
and returned in JSON; blocked, timeout, and interrupted runs keep their own
classifications; and focused tests plus strict OpenSpec validation pass.
