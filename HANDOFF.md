# Sisyphusfy Handoff

## Current goal

Release-ready codebase with distribution and installation support.

## Current status

- MIT License selected.
- OpenSpec initialized for OpenCode and CodeBuddy workflows.
- 16 changes archived: minimal-runner, durable-iteration-loop, agent-adapters-and-model-fallback, workflow-integrations, optional-archive-commit-hooks, audit-and-fix-agent-workflow, repair-final-workflow-safety, improve-human-friendly-cli, add-distribution-and-installers, repair-distribution-release-gates, close-audit-identified-gaps, simplify-verification-failures, stream-progress-with-explicit-timing, stop-on-agent-failure, render-commands-unambiguously, diagnose-agent-provider-failure.
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
- Automatic OpenSpec change discovery, task/handoff file detection, and marker-based verification command discovery.
- **Verification discovery is marker-aware.** `find_verification_command()` keeps its signature, but selection moved to ordered detectors in `src/sisyphusfy/config.py`: .NET (`*.sln` / `*.csproj` -> `dotnet test <marker>`), Rust (`Cargo.toml` -> `cargo test`), Python (pytest markers or a `tests/` directory -> `pytest`), JavaScript (`package.json` with a `test` script -> `npm test`), Flutter/Dart (`pubspec.yaml` -> `flutter test`), and a Makefile that declares a `test:` target -> `make test`. A detector requires both its project marker and its executable, so an installed `make` can no longer make a .NET repository resolve to `make test`. Detection is read-only, never runs a candidate verifier, never uses a shell, and stops (instead of falling through) when a marker exists but cannot be read. `resolve_verification()` returns the command plus a `configured` / `discovered` / `unavailable` source.
- **Verification failures are diagnosable.** Each verification invocation retains a bounded `VerificationEvidence` (command, working directory, exit status, classification, timeout flag, duration, source, detector, truncated streams) in `LoopResult`, and writes its complete stdout/stderr to `<project>/.sisyphusfy/logs/verification-<timestamp>-<pid>-i<iteration>.log` with the newest 20 files kept (`src/sisyphusfy/diagnostics.py`). Logs record no environment values and are never committed or archived by Sisyphusfy.
- **A failed agent stops the loop.** A non-zero agent exit stops the iteration with `LoopStopReason.AGENT_FAILED`, before verification and before hooks, whether or not `model_chain` is configured; the previous `and config.model_chain` guard let `dotnet test` run after `opencode` had already died. Verification now runs only after an iteration exits zero, which is what the `iteration-loop` spec always required. `command_not_found`, `interrupted`, `timed_out`, and `blocked` keep priority. With a chain, a non-retryable failure stops as `agent_failed` without advancing; `models_exhausted` is reserved for an all-retryable chain and now also retains its last attempt's evidence.
- **Agent errors are recovered, persisted, and displayed.** `AgentAdapter` gained `parse_error(output)`; the built-ins share `parse_error_envelope()`, which reads the first balanced JSON object carrying a `name` from the combined stdout+stderr and returns `name` / `message` / `reference` (`data.message`, `data.ref`). The loop calls it defensively, so a third-party adapter without the method degrades to no structured error. The error and the failed run's `agent_evidence` (command, exit status, bounded output, log path) are returned in `LoopResult.agent_error` / `agent_evidence` and JSON, and printed as `[agent] failed: …`, `[agent] error: …`, `[agent] reference: …`, `[agent] diagnostics: …`. `--verbose` prints the agent log when no verification evidence exists, so the inspect instruction stays truthful.
- **Live progress streams while subprocesses run.** `src/sisyphusfy/progress.py` adds one duration formatter (`format_duration`: `0s`, `42s`, `1m 12s`), a `ProgressSink` protocol, and a `StreamProgress` human sink. `run_agent()` streams line-oriented output through optional callbacks, emits a heartbeat when a subprocess has been quiet for the heartbeat interval (15s by default), and still captures the full streams for evidence. Progress is written to **stderr** so the concise human result on stdout and `--json` output stay unchanged; JSON never contains progress lines. The loop labels agent output `[agent]` and verification output `[verify]`.
- **Timeouts report immediately.** A timeout prints the component, the limit with explicit units, the last bounded output, and the diagnostic log path before the resume instruction. An agent timeout keeps its own `agent_evidence` (command, exit status, partial output, log path) on `LoopResult`.
- **Ctrl-C is a structured stop.** `Classification.INTERRUPTED`, `RunResult.interrupted`, and `LoopStopReason.INTERRUPTED` classify an interrupt: the runner terminates the child, keeps whatever output arrived, and the loop returns without running archive or commit hooks and without touching task or handoff state. `main()` exits 130 with a short message.
- **Output is concise by default.** `run` and `resume` print the verifier, its status, the diagnostic log path, and the resume instruction; `--verbose` (also on `loop`) prints the saved streams. JSON carries `verification` metadata (source, detector, status, exit status, timeout flag, log path) and reports `status: skipped` / `source: unavailable` when no verifier was resolved. `doctor` and `--dry-run` show the resolved source and command before a run.
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
- **First stable release is fully published.** Run `33362030032` on tag `v0.1.0` completed all four `build-artifacts` jobs, `publish-release`, `publish-pypi`, `test-installers`, `test-powershell`, `verify-powershell-syntax`, and `verify-links` successfully. GitHub Release `v0.1.0` carries `SHA256SUMS.txt` and `sisyphusfy-0.1.0-{linux-x86_64,darwin-x86_64,darwin-aarch64,win32-x86_64}.tar.gz`; PyPI carries the wheel and sdist.
- Public contracts documented: `docs/configuration.md` (every TOML field with type, default, precedence, safety, plus verification discovery precedence and diagnostic-log behavior), `docs/adapters.md`, `docs/examples.md`, `docs/ci.md` (CI usage and the JSON `verification` block), `docs/security.md` (command-execution model, read-only detection, bounded diagnostics, and review checklist).
- GitHub Pages deployment documentation in `docs/deployment.md`.
- **Commands render with unambiguous quoting.** A single shared `format_command()` (next to `RunResult` in `src/sisyphusfy/result.py`) uses `shlex.join`, so a multi-word argument such as the default agent prompt appears as one quoted token (`opencode run 'Read … and any handoff …'`) instead of a space-joined line that looks like a missing quote. It is used in the diagnostic log header, the `doctor`/dry-run verification description, the timeout report (agent and verification), the verification status line, and the low-level CLI output. Simple commands such as `dotnet test App.sln` render unchanged, and JSON keeps `command` as a list. The formatter is display-only and is never passed to a process, so the no-shell guarantee is untouched.
- **Provider-side agent failures are self-diagnosing.** A generic server error from the agent CLI (e.g. opencode `UnknownError` with an `err_*` reference) used to be an opaque dead-end that looked like a sisyphusfy bug. `AgentError` gained an optional `hint`; each adapter implements `diagnostic_hint()` (opencode: `opencode run 'hi' --print-logs --log-level DEBUG`), and `loop._parse_agent_error` attaches it only when the error is a generic provider-side server error (detected by name/`server logs` token, never agent-specific). `human._print_agent_failure` reports `this is an agent-CLI/provider error, not a sisyphusfy failure` plus the diagnose command, and the hint is included in JSON. Specific agent errors (e.g. `RateLimitError`) get no hint so the real error stays prominent. `docs/troubleshooting.md` documents the `UnknownError`/`err_*` class with the exact diagnostic steps. Sisyphusfy does not mutate the agent CLI's files (no auto-install); it only points the user at the real cause.
- 563 tests across 45 test files: `tests/test_progress.py` covers duration formatting, component-labelled streaming, idle heartbeats, timeout reporting, interruption, bounded output, and clean JSON; `tests/test_agent_failure.py` covers stopping on a non-zero agent exit with and without a model chain, that the verifier never runs, error recovery from either stream, evidence retention, and classification priority; `tests/test_human_agent_failure.py` covers the failure report, JSON shape, and `--verbose` agent diagnostics; `tests/test_render_commands.py` covers the formatter quoting a multi-word argument, leaving simple commands unchanged, the diagnostic-log header, the timeout and verification-status lines, and JSON keeping `command` as a list; `tests/test_agent_error_hint.py` covers provider-side errors getting the adapter's diagnostic hint (and specific errors getting none), the per-adapter hint commands, the `hint` round-trip in JSON, and the human report. `ruff check` clean; `compileall` clean; `openspec validate --all --strict` passes.
- Package builds cleanly.

## Next action

The first stable release is published: `v0.1.0` on GitHub with the four platform archives and checksums, and `sisyphusfy==0.1.0` is available on PyPI. It was produced entirely by CI from the tag.

1. Bump `sisyphusfy.__version__` and re-tag for the next release; `tests/test_version_sync.py` keeps the npm manifest, npm launcher, and both installers in step.

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
- An explicitly configured `verification_command` always wins over discovery; discovery is a convenience, not a contract for a release gate.
- Verification diagnostics are bounded: results keep truncated streams, logs keep everything with the 20 newest files retained, and full output requires `--verbose` or reading the log.
- Progress and heartbeats go to stderr, so streaming never changes the concise human result or the JSON contract; `--json` disables the progress sink entirely.
- Every human-facing duration names its units (`42s`, `1m 12s`); a bare number or unitless clock value is never printed.
- Commands shown to humans are quoted with `shlex.join` so a multi-word argument reads as one token; quoting is display-only and never changes what executes.
- A generic server error from the agent CLI (e.g. opencode `UnknownError`) is annotated with an adapter-specific diagnostic hint, because the real cause is almost always the user's agent-CLI provider/config, not sisyphusfy. Sisyphusfy never auto-installs agent-CLI provider packages or edits the agent CLI's files; it only points at the cause.
- A heartbeat reports that a subprocess produced no output; it is not evidence that the subprocess is healthy.
- An interruption is reported as `interrupted` and never runs archive or commit hooks, so a Ctrl-C cannot publish unverified work.
- A non-zero agent exit is a failure: the loop stops, verification does not run, and no hook is invoked. Verification is evidence about an iteration that produced something, never about one that died.
- Recovering an agent error is best-effort and lives in adapters; the stop reason stands on the exit status alone when nothing recognizable is printed.
- Marking a run `blocked` requires a blocked marker even when the exit status is non-zero; the agent asking for a decision is more actionable than a generic failure.
- A passing verification command proves that command passed, not that the product works end to end.
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
