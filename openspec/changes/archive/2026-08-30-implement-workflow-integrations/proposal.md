# Proposal: Add Workflow Integrations

## Why

The loop needs reusable ways to determine progress across unrelated projects. OpenSpec is important for the primary use case, but the public tool must also support ordinary Markdown plans, JSON state, and project-owned verification commands.

## New

- Markdown checkbox state adapter.
- JSON predicate state adapter.
- OpenSpec change adapter.
- Configurable verification command and completion predicate.
- Concise handoff prompt and state-change checks.

## Non-goals

- No agent-provider logic.
- No automatic Git operations.
- No assumptions about project source files or programming language.
- No generated handoff history or transcript storage.
