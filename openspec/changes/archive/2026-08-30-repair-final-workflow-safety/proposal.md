# Proposal: Repair Final Workflow Safety and Specification Integrity

## Why

The latest audit found four release-blocking gaps despite green tests: two archived capabilities produce invalid main-spec format, loop dry-run still executes the agent, commit allowlists are not applied to staging, and model fallback may retain the original model. CodeBuddy command compatibility also lacks an integration-level contract.

## New

- Valid archived main specs with `Purpose` and `Requirements` sections.
- A dry-run guarantee covering agent, verification, workflow, archive, and commit processes.
- Actual allowlisted Git staging behavior.
- Reliable model replacement for every fallback attempt.
- Fake-CLI contract tests for OpenCode and CodeBuddy invocation.

## Modified

- Specification, loop, adapter, hook, test, and release-documentation behavior.

## Non-goals

- No new provider integration.
- No automatic permission approval.
- No push support.
- No conversation continuation.
- No unrelated refactoring or product features.
