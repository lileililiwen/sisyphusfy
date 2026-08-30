# Proposal: Implement the Durable Iteration Loop

## Why

The minimal runner can execute one process, but it cannot resume work after a model failure or keep context bounded across sessions. This change adds the generic supervisor loop that uses project state files as the durable boundary.

## New

- Configurable task-state and handoff files.
- One-task-per-iteration execution.
- Verification, timeout, max-iteration, unchanged-state, complete, and blocked stop conditions.
- Human-readable and machine-readable loop results.

## Non-goals

- No named agent or model provider integrations.
- No OpenSpec-specific parsing.
- No Git archive, commit, or push operations.
- No automatic approval of agent permissions.
