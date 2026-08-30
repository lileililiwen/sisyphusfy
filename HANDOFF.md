# Sisyphusfy Handoff

## Current goal

Release-ready codebase with passing quality gates.

## Current status

- MIT License selected.
- OpenSpec initialized for OpenCode and CodeBuddy workflows.
- 8 changes archived: minimal-runner, durable-iteration-loop, agent-adapters-and-model-fallback, workflow-integrations, optional-archive-commit-hooks, audit-and-fix-agent-workflow, repair-final-workflow-safety, improve-human-friendly-cli.
- Main specs synced: `minimal-runner`, `iteration-loop`, `agent-adapters`, `workflows`, `agent-workflow`, `workflow-safety`, `human-cli`.
- All main specs use canonical `## Purpose` / `## Requirements` format.
- Durable iteration loop in `src/sisyphusfy/loop.py` with dry-run propagation through agent, verification, and hook boundaries.
- CLI `loop` subcommand in `src/sisyphusfy/cli.py`.
- Agent adapters in `src/sisyphusfy/adapters.py` with fresh command construction per fallback model.
- Completion hooks in `src/sisyphusfy/hooks.py` with commit path canonicalization, escape rejection, and allowlisted git staging.
- Workflow adapters reload state between observations.
- Default token-efficient prompt; blocked-signal detection on stdout and stderr.
- Human-friendly CLI: `init`, `run`, `resume`, `status`, `doctor` subcommands.
- Project configuration in `.sisyphusfy.toml` with precedence: CLI > project > user defaults > built-in.
- Automatic OpenSpec change discovery, task/handoff file detection, and verification command auto-detection.
- Human-readable progress, fallback, blocker, and next-action output with JSON compatibility.
- 297 tests across 23 test files; `ruff check` clean; `compileall` clean; `openspec validate --all --strict` passes.
- Package builds cleanly.

## Next action

All tasks complete. Ready for release or further feature work.

## Verification gates

```bash
openspec validate --all --strict
.venv/bin/pytest tests/ -v
.venv/bin/ruff check src/sisyphusfy/ tests/
.venv/bin/python -m compileall src/sisyphusfy/
```

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
- Commit hook canonicalizes paths and rejects escapes before staging.
- Model fallback constructs a fresh command per model; non-retryable failures stop the chain.
- Dry-run mode skips all subprocess execution: agent, verification, workflow, archive, commit.
- Adapter registry is extensible for custom adapters.
- Credentials come from the environment or agent configuration and are never printed.
