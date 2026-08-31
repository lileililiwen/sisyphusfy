# Sisyphusfy Handoff

## Current goal

Release-ready codebase with distribution and installation support.

## Current status

- MIT License selected.
- OpenSpec initialized for OpenCode and CodeBuddy workflows.
- 11 changes archived: minimal-runner, durable-iteration-loop, agent-adapters-and-model-fallback, workflow-integrations, optional-archive-commit-hooks, audit-and-fix-agent-workflow, repair-final-workflow-safety, improve-human-friendly-cli, add-distribution-and-installers, repair-distribution-release-gates, close-audit-identified-gaps.
- Main specs synced: `minimal-runner`, `iteration-loop`, `agent-adapters`, `workflows`, `agent-workflow`, `workflow-safety`, `human-cli`, `distribution`, `distribution-quality`, `supervisor-quality`.
- All main specs use canonical `## Purpose` / `## Requirements` format.
- `distribution` main spec normalized to canonical `## Purpose` / `## Requirements` (removed change-delta `## ADDED Requirements` header) while preserving all five requirements and scenarios.
- New `distribution-quality` main spec records the ongoing release-gate requirements: canonical distribution main spec, archive-safe documentation tests, and honest PowerShell verification reporting.
- Documentation link tests read stable README and the canonical `distribution` main spec instead of an active change directory, so they keep passing after a change is archived.
- PowerShell installer verification runs syntax + fixture checks when a supported PowerShell runtime is available and skips explicitly (never silently passes) when none is present. Runtime detection probes that the binary actually executes (not just `shutil.which` presence) so a non-executable wrapper such as a broken Snap stub is reported as unavailable rather than producing a false failure. `release.yml` adds a `verify-powershell-syntax` job that distinguishes an unavailable (or non-executable) runtime from a script failure.
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
- Distribution module in `src/sisyphusfy/distribution.py` with release metadata, checksum generation, and artifact management.
- npm launcher package in `npm/` for cross-platform installation without Python.
- POSIX shell installer (`install.sh`) with version override and dry-run support.
- PowerShell installer (`install.ps1`) for Windows with TLS 1.2 and checksum verification.
- GitHub Actions release CI in `.github/workflows/release.yml` for multi-platform artifact builds and checksums.
- **Release artifacts are real executables.** `build-artifacts` builds a single-file `sisyphusfy` (or `sisyphusfy.exe` on Windows) with PyInstaller from `src/sisyphusfy/cli.py` and packages only that binary into `sisyphusfy-<version>-<platform>-<arch>.tar.gz`. This matches the installer contract (extract to `~/.sisyphusfy/bin` and exec the binary) instead of the previous behavior that tarred the `dist/` wheel/sdist, which contained no runnable command.
- **Release targets are a single source of truth.** `src/sisyphusfy/distribution.py` defines `RELEASE_TARGETS`, `DEFERRED_TARGETS`, and `RUNNER_NATIVE_ARCH`; release metadata, the CI matrix, `install.sh`, and the npm launcher must all agree with it. `tests/test_release_targets.py` fails when they diverge.
- **Deferred release target:** `linux/aarch64` is no longer advertised. It was previously built on `ubuntu-latest` (x86_64) and published as an aarch64 artifact. It stays in `DEFERRED_TARGETS` until an aarch64 runner or a verified cross-compilation process exists; on that platform use `pip install sisyphusfy`. `darwin/x86_64` builds on the Intel runner `macos-15-intel`, not on an arm64 runner, for the same reason. The first release attempt used the retired `macos-13` label and its job stayed queued until the run was cancelled.
- **One verification per iteration.** `run_loop` runs the configured verification at most once per productive iteration and always before completion is accepted or hooks run, including when task state is already complete on entry.
- **Dry-run executes nothing.** Low-level dry-run skips the agent, verification, external completion checks, workflow validation, and hooks. When completion cannot be evaluated without running a command, the loop stops with `dry_run` instead of claiming a completion state it did not verify.
- **Project directory propagation.** `run`, `resume`, and `loop` resolve the project directory once and use it as the working directory for agents, verification, workflow validation, and archive/commit hooks. Relative task, handoff, workflow, and hook paths resolve against it.
- **Completion checks run in the project directory.** The loop scopes the built-in external completion strategy to its working directory (an explicit strategy directory still wins), so `sisyphusfy loop -d <project> --completion-strategy external` checks inside `<project>`.
- **Missing commands are structured failures.** `run_agent()` classifies a missing executable as `command_not_found` (exit status 127) and the loop reports a `command_not_found` stop reason naming the command, for agent, verification, and completion-check commands. No call site raises an unhandled `FileNotFoundError`.
- **Release version metadata has one source of truth.** `sisyphusfy.__version__` is the Python-side source; `pyproject.toml` reads it through setuptools dynamic metadata, and `tests/test_version_sync.py` asserts the npm manifest, npm launcher, and both installers agree. `release.yml` fails the publish job when the Git tag disagrees with the packaged version.
- **Known release gap — PyPI publication.** `release.yml` now has a `publish-pypi` job that builds the sdist/wheel and uploads them with `pypa/gh-action-pypi-publish` using trusted publishing (`id-token: write`, no API token). It needs `publish-release`, so a failed GitHub Release never publishes a package. What is still missing is external: register the `sisyphusfy` project on PyPI and configure a trusted publisher for this repository plus the `pypi` environment. Until that is done the job fails loudly instead of being skipped, by design.
- **Known release gap — first release.** The repository is public at https://github.com/lileililiwen/sisyphusfy with `origin` configured and `main` pushed. The remote tag `v0.1.0` exists and points at `b70048a`. The first release attempt (run `33360138351`) was cancelled: every build finished except `darwin/x86_64`, whose `macos-13` runner never scheduled. The matrix now uses `macos-15-intel`, the tag is being re-pointed at the fix, and the release is retried. No GitHub Release exists yet.
- Public contracts documented: `docs/configuration.md` (every TOML field with type, default, precedence, safety), `docs/adapters.md` (agent and workflow adapter protocols, registry, model fallback, failure classification), `docs/examples.md` (Python, Rust, JavaScript, Flutter, .NET), `docs/ci.md` (CI usage), `docs/security.md` (command-execution model and review checklist).
- GitHub Pages deployment documentation in `docs/deployment.md`.
- 442 tests across 38 test files (441 passed + 1 skipped with no usable PowerShell runtime, 442 passed where one is available); `ruff check` clean; `compileall` clean; `openspec validate --all --strict` passes. The PowerShell installer syntax check runs when a runnable PowerShell runtime is present and is reported as skipped (not passed, not failed) when none is available.
- Package builds cleanly.

## Next action

Implementation and documentation gaps are closed; `main` and the `v0.1.0` tag are pushed to the public repository. Two external steps remain:

1. Retry the release: `origin/main` now builds `darwin/x86_64` on `macos-15-intel`, so re-point `v0.1.0` at the fix commit and let CI produce the artifacts, checksums, and GitHub Release. The tag must match `sisyphusfy.__version__` or the release job fails.
2. Register the `sisyphusfy` project on PyPI and add a trusted publisher for this repository and the `pypi` environment. Until then the `publish-pypi` job fails loudly on every tag push, by design.

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
- Verification runs after each productive iteration but before accepting completion; it never runs twice for the same iteration.
- Completion hooks run only after both completion and verification succeed; an already-complete project still verifies before hooks run.
- Default prompt directs one task, handoff update, and safe stop on blockers.
- Blocked detection covers stdout and stderr; ordinary failures are not blocked.
- Commit hooks require explicit `allowed_files` to prevent staging unrelated files.
- Commit hook canonicalizes paths and rejects escapes before staging.
- Model fallback constructs a fresh command per model; non-retryable failures stop the chain.
- Dry-run mode skips all subprocess execution: agent, verification, workflow, archive, commit, and external completion checks. When completion needs a command, dry-run reports `dry_run` rather than a guessed state.
- The selected project directory is the working directory of every subprocess, and relative configured paths resolve against it.
- Adapter registry is extensible for custom adapters.
- Credentials come from the environment or agent configuration and are never printed.
- Distribution artifacts use SHA-256 checksums and HTTPS-only downloads.
- Installers default to user-writable directories; root installation is explicit.
- npm launcher downloads platform-specific releases without reimplementing Python runner logic.
- A release target is published only when CI can build it on a runner with that native architecture; otherwise it is deferred and installers refuse it.
