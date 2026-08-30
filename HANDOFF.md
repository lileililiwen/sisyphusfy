# Sisyphusfy Handoff

## Current goal

Release-ready codebase with distribution and installation support.

## Current status

- MIT License selected.
- OpenSpec initialized for OpenCode and CodeBuddy workflows.
- 10 changes archived: minimal-runner, durable-iteration-loop, agent-adapters-and-model-fallback, workflow-integrations, optional-archive-commit-hooks, audit-and-fix-agent-workflow, repair-final-workflow-safety, improve-human-friendly-cli, add-distribution-and-installers, repair-distribution-release-gates.
- Main specs synced: `minimal-runner`, `iteration-loop`, `agent-adapters`, `workflows`, `agent-workflow`, `workflow-safety`, `human-cli`, `distribution`, `distribution-quality`.
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
- **Known release limitation:** the `linux/aarch64` matrix entry still builds on `ubuntu-latest` (x86_64), so its tarball currently ships an x86_64 binary mislabeled aarch64. Cross-arch builds (qemu/emulation or arm runners) are not yet wired up; aarch64 users should use the x86_64 artifact or `pip install sisyphusfy` for now.
- GitHub Pages deployment documentation in `docs/deployment.md`.
- 367 tests across 30 test files (local run with a working PowerShell runtime); `ruff check` clean; `compileall` clean; `openspec validate --all --strict` passes. The PowerShell installer syntax check runs when a runnable PowerShell runtime is present and is reported as skipped (not passed, not failed) when none is available, so the count is 367 passed on this host and 366 passed + 1 skipped on a host without a usable runtime.
- Package builds cleanly.

## Next action

Release gate repaired: distribution main spec is canonical, documentation link tests are archive-safe, PowerShell verification reports honestly, and release artifacts are now real executables that match the installer contract. Not yet marked release-ready: a GitHub Release must be produced by CI (PyInstaller builds + checksum publishing) and the `linux/aarch64` cross-build limitation should be resolved before publishing that specific artifact.

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
- Distribution artifacts use SHA-256 checksums and HTTPS-only downloads.
- Installers default to user-writable directories; root installation is explicit.
- npm launcher downloads platform-specific releases without reimplementing Python runner logic.
