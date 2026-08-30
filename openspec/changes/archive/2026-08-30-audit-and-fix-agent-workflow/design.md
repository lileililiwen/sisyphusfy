# Design: Audit and Fix the Agent Workflow

## Explore & Reuse

Reuse `run_agent` for subprocess lifecycle and timeout handling, `AgentAdapter` for agent-specific command construction, `run_loop` for iteration orchestration, workflow adapters for completion state, and completion hooks for optional archive/commit actions. Do not add a second subprocess path or duplicate state parsing.

## Required corrections

1. Each named adapter must produce the actual non-interactive invocation for its supported CLI, with the prompt delivered according to that CLI's contract and no continuation/session flag.
2. Workflow adapters must reload task/state files for every observation and snapshot; in-memory caches may not make modified state invisible.
3. After a productive agent iteration, run verification before accepting completion. Completion hooks run only after completion and verification both succeed.
4. Provide a short default prompt referencing configured instruction, task, and handoff paths. It must direct one task, handoff update, and safe stop on blockers.
5. Detect blocked outcomes from configured exit status and structured/standard output streams without treating ordinary test failures as permission blocks.
6. Commit hooks must enforce explicit allowlisted paths before staging and reject or skip anything outside the allowlist. Archive and commit commands remain disabled by default.

## Verification strategy

Add integration tests around fake agent executables, mutable task files, fake verification/archive/Git commands, and temporary repositories. Include at least one smoke test for each supported named adapter's final argv. Tests must not require real OpenCode, CodeBuddy, Docker, network access, or credentials.

## Scope boundary

This is a planning-only correction change. The implementation agent must not broaden it into provider onboarding, UI, packaging redesign, or push automation.
