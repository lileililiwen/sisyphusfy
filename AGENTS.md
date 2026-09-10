# Sisyphusfy Agent Instructions

## Purpose

Sisyphusfy is a project-agnostic supervisor for disposable AI-agent sessions. It must work with different languages, repository layouts, task formats, agent CLIs, and model providers.

## Development workflow

All product changes use OpenSpec:

```text
propose → validate → implement → verify → archive
```

Read `openspec/config.yaml`, the active change, and relevant source before implementation. Do not implement a change until its `design.md` has human approval.

## Change completion workflow

After `verify` passes (focused tests, full suite, `ruff check`, `compileall`, `openspec validate --all --strict`), close out the change in two commits so the change history is decoupled from the meta-status history:

1. Mark every task in `tasks.md` complete (`[x]`).
2. Archive the change with `openspec archive <name> --yes`. This moves the
   `openspec/changes/<name>/` directory to `openspec/changes/archive/<date>-<name>/`
   and drops the delta spec.
3. Stage the implementation, tests, docs, the spec sync, `tasks.md`, and the
   archived change directory. Commit as **commit 1** with a message that names
   the OpenSpec change, for example
   `Harden agent adapter and fallback contracts (OpenSpec change harden-agent-adapter-and-fallback-contracts)`.
4. Update `HANDOFF.md`: increment the archived-change count, add a status
   bullet, remove the change from the active remediation queue, and refresh
   the "Next action" / dependency order.
5. Stage the `HANDOFF.md` change and commit as **commit 2** with a message
   such as `Update HANDOFF: archive <change-name>`.

This two-commit split keeps the change itself reviewable on its own and
makes the meta-status history easy to skim. It is the default local
workflow. Push, tag, and release still require explicit user authorization.

## Core boundaries

- Keep the loop engine independent of OpenCode, CodeBuddy, OpenSpec, Git, and any programming language.
- Put agent-specific behavior in adapters.
- Put task-format behavior in state adapters.
- Treat verification results as evidence; never replace them with agent claims.
- Keep prompts short and reusable.
- Never silently approve privileged or destructive operations.
- Do not push, tag, or release unless explicitly requested.

## Quality

- Tests are required for new behavior and should use fake agent commands where possible.
- Every subprocess needs timeout and exit-status handling.
- User-controlled command execution must be documented and tested.
- Preserve clear errors and structured results for automation.
