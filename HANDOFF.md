# Sisyphusfy Handoff

## Current goal

Implement the durable iteration loop for multi-step agent sessions.

## Current status

- MIT License selected.
- OpenSpec initialized for OpenCode and CodeBuddy workflows.
- Change `implement-minimal-runner` archived to `openspec/changes/archive/2026-08-30-implement-minimal-runner/`.
- Change `implement-durable-iteration-loop` archived to `openspec/changes/archive/2026-08-30-implement-durable-iteration-loop/`.
- Change `implement-agent-adapters-and-model-fallback` archived to `openspec/changes/archive/2026-08-30-implement-agent-adapters-and-model-fallback/`.
- Main specs synced: `minimal-runner`, `iteration-loop`, and `agent-adapters`.
- Durable iteration loop implemented in `src/sisyphusfy/loop.py`.
- CLI extended with `loop` subcommand in `src/sisyphusfy/cli.py`.
- Agent adapters implemented in `src/sisyphusfy/adapters.py`.
- Loop features: fresh process per iteration, Markdown checkbox and external-command completion strategies, task/handoff state snapshots, verification, timeout, max-iteration, unchanged-state, and blocked stop conditions.
- Adapter features: registry, OpenCode/CodeBuddy/Generic adapters, model-chain fallback, retryable/non-retryable failure classification.
- JSON and human-readable loop output.
- Optional completion hooks for OpenSpec archive and Git commit implemented in `src/sisyphusfy/hooks.py`.
- Hook features: disabled by default, dry-run support, explicit file allowlist, structured results, failure stops pipeline.
- Current test result: `141 passed`.
- `ruff check` passes on all source and test files.
- `compileall` passes on all source files.
- Package installs cleanly (`pip install -e .`).
- All tasks complete. Change validated with `openspec validate --strict`.

## Next action

Ready for archive or commit. Pending changes: `implement-workflow-integrations`.

## Verification gates

```bash
openspec validate implement-agent-adapters-and-model-fallback --strict
.venv/bin/pytest tests/ -v
.venv/bin/ruff check src/sisyphusfy/ tests/
```

Before archive, run the focused test suite twice, packaging/quality checks, and the configured verification command. Do not commit, archive, or push until those checks pass.

## Known decisions

- Fresh sessions are the default to avoid accumulating conversation-token cost.
- Model fallback is ordered configuration, not constants.
- Permission requests and ambiguous choices must stop safely rather than receive guessed answers.
- Loop stops with UNCHANGED_STATE when no completion strategy is configured and the agent does not modify state.
- Completion strategy check runs before state-change check so completed work is detected immediately.
- Verification timeout returns TIMEOUT classification (distinct from VERIFICATION_FAILED).
- Credentials come from the environment or agent configuration and are never printed.
- Adapter registry is extensible for custom adapters.
