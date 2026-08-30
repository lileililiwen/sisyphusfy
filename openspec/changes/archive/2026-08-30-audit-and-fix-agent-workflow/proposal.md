# Proposal: Audit and Fix the Agent Workflow

## Why

The completed runner, loop, adapters, workflow integrations, and hooks pass their unit tests, but a repository audit found gaps between tested abstractions and the intended real-world workflow. OpenCode command construction is incompatible with the installed CLI shape, workflow adapters can read stale state, completion can bypass verification, the default prompt is empty, blocked detection is narrow, and commit allowlists are not enforced.

## New

- Correct real agent command contracts for fresh non-interactive sessions.
- Per-iteration state reload and reliable completion ordering.
- A token-efficient default prompt and robust blocked outcome detection.
- Enforced commit file allowlists and evidence-based hook behavior.
- End-to-end tests using fake agent CLIs and temporary repositories.

## Modified

- Agent adapter, loop, workflow, hook, CLI, and documentation behavior.

## Non-goals

- No new agent provider integration beyond correcting existing adapters.
- No automatic permission approval.
- No conversation continuation or transcript persistence.
- No push support.
- This change records the planned fix only; implementation is intentionally deferred.
