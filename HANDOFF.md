# Sisyphusfy Handoff

## Current goal

Audit and fix the agent workflow to match real-world CLI contracts.

## Current status

- MIT License selected.
- OpenSpec initialized for OpenCode and CodeBuddy workflows.
- Changes `implement-minimal-runner`, `implement-durable-iteration-loop`, `implement-agent-adapters-and-model-fallback`, `implement-workflow-integrations`, and `implement-optional-archive-commit-hooks` archived.
- Main specs synced: `minimal-runner`, `iteration-loop`, `agent-adapters`, `workflows`.
- Durable iteration loop implemented in `src/sisyphusfy/loop.py`.
- CLI extended with `loop` subcommand in `src/sisyphusfy/cli.py`.
- Agent adapters implemented in `src/sisyphusfy/adapters.py`.
- Loop features: fresh process per iteration, Markdown checkbox and external-command completion strategies, task/handoff state snapshots, verification before completion, timeout, max-iteration, unchanged-state, and blocked stop conditions.
- Adapter features: registry, OpenCode/CodeBuddy/Generic adapters, model-chain fallback, retryable/non-retryable failure classification.
- OpenCode adapter uses `opencode run --model <model>` (no `-c`/`-s`).
- CodeBuddy adapter uses `codebuddy -p` (no `-c`/`-r`).
- Workflow adapters reload state via `reload()` method between observations.
- Default token-efficient prompt when no custom template is configured.
- Blocked-signal detection covers both stdout and stderr.
- Commit hooks enforce explicit `allowed_files`; empty allowlist is refused.
- JSON and human-readable loop output.
- Optional completion hooks for OpenSpec archive and Git commit implemented in `src/sisyphusfy/hooks.py`.
- Hook features: disabled by default, dry-run support, explicit file allowlist, structured results, failure stops pipeline.
- Current test result: `209 passed`.
- `ruff check` passes on all source and test files.
- `compileall` passes on all source files.
- Package installs cleanly (`pip install -e .`).
- All tasks complete. Change validated with `openspec validate --strict`.

## Next action

Ready for archive or commit. Pending change: `audit-and-fix-agent-workflow`.

## Verification gates

```bash
openspec validate audit-and-fix-agent-workflow --strict
.venv/bin/pytest tests/ -v
.venv/bin/ruff check src/sisyphusfy/ tests/
```

Before archive, run the focused test suite twice, packaging/quality checks, and the configured verification command. Do not commit, archive, or push until those checks pass.

## Known decisions

- Fresh sessions are the default to avoid accumulating conversation-token cost.
- OpenCode uses `opencode run` (not `--non-interactive`) for non-interactive invocation.
- CodeBuddy uses `codebuddy -p` (not `--non-interactive`) for non-interactive output.
- No continuation flags (`-c`, `-s`, `-r`) are passed to preserve fresh sessions.
- Workflow adapters reload from disk on each observation to detect external changes.
- Verification runs after each productive iteration but before accepting completion.
- Completion hooks run only after both completion and verification succeed.
- Default prompt directs one task, handoff update, and safe stop on blockers.
- Blocked detection covers stdout and stderr; ordinary failures are not blocked.
- Commit hooks require explicit `allowed_files` to prevent staging unrelated files.
- Model fallback is ordered configuration, not constants.
- Permission requests and ambiguous choices must stop safely rather than receive guessed answers.
- Credentials come from the environment or agent configuration and are never printed.
- Adapter registry is extensible for custom adapters.
