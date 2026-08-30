# Proposal: Implement the Minimal Runner

## Why

Sisyphusfy needs a small, reliable execution core before it can support model fallback, OpenCode, CodeBuddy, and other agent CLIs. The first slice should establish the process boundary and verification evidence without coupling the project to one agent or repository type.

## What changes

### New

- A CLI command that runs one configured agent iteration in a selected working directory.
- Configurable prompt delivery, timeout, environment, and exit-status capture.
- A dry-run mode that prints the command without executing it.
- Structured result data for later loop, retry, and blocked-state handling.

### Modified

- None.

## Non-goals

- No OpenCode or CodeBuddy-specific behavior in the core.
- No model fallback yet.
- No automatic task parsing, archive, commit, or push.
- No assumption about programming language or project layout.
