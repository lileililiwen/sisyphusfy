# Design: Close the remaining post-commit audit gaps

## Explore & Reuse

- Reuse `run_agent()` as the single bounded subprocess runner; add a missing-executable classification there instead of adding try/except at every call site.
- Reuse the working-directory scoping pattern already used for completion hooks (`_hooks_with_directory`) and workflow configs (`_scoped_workflow_config`) for the completion strategy, so directory propagation has one home: `run_loop`.
- Reuse `LoopStopReason` for structured failures; add `command_not_found` rather than overloading `verification_failed` or `adapter_error`.
- Reuse the existing `WorkflowError` handling path for completion-check failures raised by workflow adapters.
- Reuse `sisyphusfy.__version__` (new) plus setuptools dynamic versioning; do not invent a release tool.
- Preserve the project-agnostic core: no ecosystem-specific behavior is introduced.

## Behavior

`run_loop` resolves its working directory once. Before evaluating completion, it scopes the built-in `ExternalCommandCompletion` to that directory when the strategy does not carry an explicit one, mirroring hook and workflow scoping. An explicitly configured directory always wins, so a caller that needs another location keeps it.

`run_agent()` catches `FileNotFoundError` and returns a `RunResult` with classification `command_not_found` and exit status `127`, the conventional shell code for a missing executable. The loop maps that classification to a `command_not_found` stop reason with a message naming the missing command, for the agent and for verification.

Completion strategies cannot return a structured result through `has_work()`, so `ExternalCommandCompletion` raises `CompletionCheckError` for a missing or timed-out check command. `run_loop` converts that error, and any `WorkflowError` raised while evaluating completion, into the same `command_not_found` stop reason. Timeouts keep their existing `timeout` stop reason; only command availability changes classification.

`sisyphusfy.__version__` becomes the Python-side source of truth and the sdist/wheel version reads it through setuptools dynamic metadata. The npm launcher, npm manifest, POSIX installer, and PowerShell installer repeat the literal because a shell or JavaScript artifact cannot import Python; a test asserts all of them agree, so a bump cannot silently diverge. CI compares the Git tag with the package version and fails the release when they disagree.

## Error handling and safety

Missing executables, timeouts, non-zero verification, and unsupported release targets remain explicit structured failures. No shell-string interpolation and no implicit privilege escalation are introduced. The version-synchronization test and CI check fail loudly instead of publishing a mismatched artifact.

## Verification

Add regression tests for completion-check directory propagation (default and explicit), for missing agent, verification, and completion commands, and for version-metadata agreement across `pyproject.toml`, `sisyphusfy.__version__`, `npm/package.json`, `npm/lib/launcher.js`, `install.sh`, and `install.ps1`. Verify the sdist/wheel still build and report the dynamic version, then run the full suite, Ruff, compileall, and strict OpenSpec validation. Update the roadmap and handoff only after the evidence is complete.
