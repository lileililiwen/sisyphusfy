# Design: Close audited correctness and release gaps

## Explore & Reuse

- Reuse `run_agent()` as the single bounded subprocess runner.
- Reuse `LoopConfig.dry_run`, `WorkflowAdapter`, and `HookConfig` rather than adding parallel execution modes.
- Reuse the existing `SisyphusConfig` and generated `.sisyphusfy.toml` as the public configuration contract.
- Reuse the current adapter `Protocol`, registry, fake-command tests, installer tests, and release workflow.
- Preserve the project-agnostic core: project-specific behavior remains configuration, workflow adapters, or agent adapters.

## Behavior

The loop will centralize completion evaluation so dry-run returns a planned result without invoking external completion or validation commands. Each productive iteration will run configured verification at most once; completion is accepted only after that verification succeeds. Initial completion follows the same verification-before-hooks rule. Hook execution remains opt-in and dry-run remains non-executing.

High-level commands will resolve `project_dir` once and pass it as the loop working directory. Every subprocess boundary created by that path—including workflow validation and completion hooks—will execute in that directory. Relative task, handoff, and workflow paths will be resolved consistently against it.

The release contract will use one source of truth for supported platform/architecture pairs. CI must either build Linux aarch64 with a real aarch64 runner/cross-build or omit it until that is possible; it must never publish an incorrectly labeled binary. Documentation will describe the supported configuration fields, adapter methods, safe subprocess rules, and one minimal end-to-end example for each requested ecosystem.

## Error handling and safety

Missing paths, invalid configuration, unavailable commands, timeouts, non-zero verification, and unsupported release targets remain explicit structured failures. No shell-string interpolation or implicit privilege escalation will be introduced. Documentation will state that configured commands are user-controlled code and must be reviewed before enabling archive or commit hooks.

## Verification

Add focused regression tests for dry-run subprocess suppression, single verification, initial completion verification, project-directory propagation, path-relative hooks/workflows, and release-matrix consistency. Add documentation contract tests and run the existing full unit suite, Ruff, compileall, and strict OpenSpec validation.
