# Sisyphusfy Agent Instructions

## Purpose

Sisyphusfy is a project-agnostic supervisor for disposable AI-agent sessions. It must work with different languages, repository layouts, task formats, agent CLIs, and model providers.

## Development workflow

All product changes use OpenSpec:

```text
propose → validate → implement → verify → archive
```

Read `openspec/config.yaml`, the active change, and relevant source before implementation. Do not implement a change until its `design.md` has human approval.

## Core boundaries

- Keep the loop engine independent of OpenCode, CodeBuddy, OpenSpec, Git, and any programming language.
- Put agent-specific behavior in adapters.
- Put task-format behavior in state adapters.
- Treat verification results as evidence; never replace them with agent claims.
- Keep prompts short and reusable.
- Never silently approve privileged or destructive operations.
- Do not commit, archive, or push unless explicitly configured.

## Quality

- Tests are required for new behavior and should use fake agent commands where possible.
- Every subprocess needs timeout and exit-status handling.
- User-controlled command execution must be documented and tested.
- Preserve clear errors and structured results for automation.
