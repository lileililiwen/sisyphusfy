# Proposal: Close audited correctness and release gaps

## Why

The audit found that the existing tests pass while several documented contracts remain incomplete or unsafe in real use: low-level dry-run can execute external completion checks, verification can run twice in one iteration, high-level project discovery does not set the execution directory, and already-complete work can invoke hooks without verification. The roadmap also lacks a public configuration/adapter contract, practical examples, and an honest release matrix.

## What changes

- Make dry-run side-effect free at all workflow and completion boundaries.
- Establish one verification ordering rule: run verification once and before completion hooks, including pre-completed state.
- Propagate the selected project directory to all agent, verification, workflow, archive, and commit operations.
- Prevent release metadata and CI from advertising an artifact built for the wrong architecture.
- Publish the TOML configuration schema and agent-adapter protocol, plus representative project examples and command-execution security guidance.
- Add regression and contract tests for each audited behavior.

## Non-goals

- No new agent provider or workflow adapter.
- No conversation-history persistence.
- No automatic push, privileged installation, or change to the opt-in nature of archive and commit hooks.
- No implementation of unrelated roadmap features.

## Success criteria

The audited scenarios are executable in tests, strict OpenSpec validation passes, dry-run performs no subprocess work, and release documentation describes only artifacts that the CI build can produce correctly.
