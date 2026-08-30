# Design: Minimal Runner

## Explore & Reuse

The repository currently contains product documentation and OpenSpec-generated agent workflow commands, but no implementation code or reusable subprocess utility. The new runner may therefore introduce the initial process abstraction. OpenSpec remains a development workflow and must not become a runtime dependency.

## Architecture

Use a small Python package with three boundaries:

1. `cli` parses flags and prints human-readable or JSON results.
2. `runner` owns one subprocess lifecycle, timeout, environment, working directory, stdin prompt delivery, and exit classification.
3. `adapters` translate agent names and model options into commands. The first slice may expose a generic command adapter; named OpenCode and CodeBuddy adapters are subsequent changes.

The runner returns a structured result containing command metadata, exit status, timeout status, captured output locations or bounded output, and a classification. It must not decide whether a product task is complete.

## Safety

Commands are passed as an argument vector where possible. Shell interpolation is opt-in and clearly marked. Dry-run is available before execution. Every invocation has a timeout. The minimal runner does not auto-approve permissions and does not perform Git operations.

## Verification

Tests use temporary fake executables or a Python test helper. They cover success, non-zero exit, timeout, prompt delivery, working directory, environment propagation, and dry-run behavior. No real model, network service, Docker daemon, or project repository is required.
