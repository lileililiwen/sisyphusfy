# Design: Human-Friendly CLI

## Explore & Reuse

Reuse the existing loop engine, workflow adapters, agent registry, model-chain fallback, completion hooks, JSON result model, and subprocess safety rules. The new commands are a thin user-facing configuration/discovery layer; they must not duplicate loop or subprocess logic.

## User experience

`sisyphusfy init` creates an optional project configuration with conservative defaults. `sisyphusfy run <change>` resolves an OpenSpec change when present, otherwise uses configured workflow state. It discovers `AGENTS.md`/`Agents.md`, `HANDOFF.md`, and task files only when they exist or are explicitly configured. The command presents compact progress and a clear final next action.

`resume` continues from files, never from an old agent conversation. `status` performs read-only state inspection. `doctor` checks executable availability, configuration validity, task/handoff paths, and verification command readiness.

## Configuration

Use a project-local `.sisyphusfy.toml` with optional user defaults. CLI overrides have higher precedence. The configuration must allow agent name, ordered models, workflow type, handoff path, verification command, iteration limits, and hook enablement. No credential values are printed.

## Safety defaults

Dry-run, archive, and commit are explicit flags. Archive and commit remain disabled by default. Permission or ambiguity blockers stop with a readable explanation and preserve state. JSON output remains available for scripts and CI.

## Verification

Test command discovery, config precedence, OpenSpec and generic workflow detection, human output, JSON compatibility, blocker output, doctor diagnostics, and explicit hook gates using temporary projects and fake executables.
