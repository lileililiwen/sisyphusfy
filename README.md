# Sisyphusfy

Fresh agent sessions. Persistent project progress.

Sisyphusfy is a project-agnostic supervisor for AI coding agents. It runs each software task in a fresh disposable session, keeps progress in durable project files, switches models when agents fail or run out of quota, and verifies outcomes independently.

It is for developers who want repeatable agent-assisted development without coupling their projects to one model, one agent CLI, or one conversation history. Use it as a small command runner, a durable task loop, or an automation building block for OpenSpec and other repository workflows.

## What it solves

- **Fresh context:** each iteration starts a new agent process, reducing stale or expensive conversation history.
- **Durable progress:** task state and handoffs live in the project, so another session can resume the work.
- **Agent neutrality:** adapters support different agent CLIs while the loop engine stays independent of them.
- **Model fallback:** quota exhaustion, timeouts, and classified failures can move work to the next configured model.
- **Evidence-based completion:** verification commands run independently; agent claims are not treated as proof.
- **Safe automation:** dry runs, structured JSON results, timeout handling, and explicit permission boundaries support CI and local use.

## Why

AI coding sessions become expensive and fragile when conversation history grows across unrelated specifications. Sisyphusfy treats the workspace as the source of truth:

- one session performs a small unit of work;
- task state and a concise handoff are written to disk;
- failures, quota exhaustion, and timeouts can switch to another model;
- the next session reconstructs only the necessary context;
- a new specification starts with a fresh conversation.

## Design principles

1. The runner is not tied to a language, framework, repository layout, or OpenSpec.
2. Agent CLIs are adapters, not dependencies of the loop engine.
3. Task state is machine-checkable; handoff text is compact recovery context.
4. Verification is performed by the runner, not merely claimed by the agent.
5. Permission prompts and ambiguous choices stop safely instead of hanging forever.
6. Commit, archive, and push are opt-in operations.
7. Fresh context is the default; conversation continuation is explicit.

## Installation

**Repository**: https://github.com/lileililiwen/sisyphusfy
**Website**: https://sisyphusfy.dev/
**Releases**: https://github.com/lileililiwen/sisyphusfy/releases

### pip / pipx

```bash
pip install sisyphusfy
# or
pipx install sisyphusfy
```

### npm

```bash
npm install -g sisyphusfy
```

The npm launcher is published from tagged releases. If npm reports `E404` for
this package, the release has not yet been published to npm; see the
[npm publication setup](docs/deployment.md#npm-package-publication) for the
one-time maintainer configuration.

### POSIX installer

```bash
curl -fsSL https://raw.githubusercontent.com/lileililiwen/sisyphusfy/main/install.sh | sh
```

### PowerShell installer (Windows)

```powershell
irm https://raw.githubusercontent.com/lileililiwen/sisyphusfy/main/install.ps1 | iex
```

### From a checkout

```bash
pip install -e .
sisyphusfy --help
```

The package requires Python 3.10 or newer. OpenCode, CodeBuddy, and any
project-specific verification tools are installed separately.

## Quick start: one invocation

Run a command with timeout:

```bash
sisyphusfy -t 30 -- echo "hello world"
```

Dry-run (shows command without executing):

```bash
sisyphusfy --dry-run -- echo "hello world"
```

JSON output for automation:

```bash
sisyphusfy --json -- python3 script.py
```

Deliver a prompt via stdin:

```bash
sisyphusfy -p "explain this repository" -- opencode run
```

Set working directory and environment variables:

```bash
sisyphusfy -d /path/to/project -t 60 -e API_KEY=abc123 -e DEBUG=1 -- my-agent
```

## Quick start: human-friendly workflow

The high-level commands provide a simpler interface for common workflows.
They automatically discover tasks, configuration, and agent settings.

Initialize a project:

```bash
sisyphusfy init
```

Run an OpenSpec change:

```bash
sisyphusfy run my-change
```

Resume from durable state:

```bash
sisyphusfy resume
```

Check project status:

```bash
sisyphusfy status
```

Diagnose configuration issues:

```bash
sisyphusfy doctor
```

Dry-run to preview planned actions:

```bash
sisyphusfy run my-change --dry-run
```

Use JSON output for automation:

```bash
sisyphusfy status --json
```

Configuration precedence: CLI flags > `.sisyphusfy.toml` > user defaults > built-in defaults.

The selected project directory (`--project-dir`, default `.`) is the working
directory for every subprocess: agent, verification, workflow validation, and
completion hooks. Relative paths resolve against it.

## Verification

Verification is the loop's only independent evidence, so it is explicit:

```bash
sisyphusfy run my-change          # uses verification_command, then discovery
sisyphusfy doctor                 # shows the resolved verifier before a run
sisyphusfy resume --verbose       # prints saved verification diagnostics
```

When `verification_command` is empty, Sisyphusfy resolves one from project
markers, in this order: .NET (`*.sln` / `*.csproj` -> `dotnet test <path>`), Rust
(`Cargo.toml` -> `cargo test`), Python (pytest markers -> `pytest`), JavaScript
(`package.json` with a `test` script -> `npm test`), Flutter/Dart
(`pubspec.yaml` -> `flutter test`), and a Makefile that declares a `test` target
(-> `make test`). A detector selects a command only when its project marker
**and** its executable are both present, so an unrelated installed tool such as
`make` never implies `make test`. Detection is read-only: it never runs a
candidate verifier and never uses a shell. An explicit `verification_command`
always wins; see [docs/configuration.md](docs/configuration.md).

A failed verifier prints the command, its exit status, and the path of the log
that holds the complete output:

```text
verification failed: dotnet test App.sln (exit 1)
  diagnostics: .sisyphusfy/logs/verification-20260831T104500-1234-i1.log
  inspect with: sisyphusfy resume --verbose
resume with: sisyphusfy resume
```

Logs live in `<project>/.sisyphusfy/logs/`, one file per run and iteration, with
the newest 20 kept. They are local diagnostics: Sisyphusfy never commits or
archives them, and it records no environment values. Default output stays
concise and JSON carries bounded metadata only; use `--verbose` to read the
saved streams.

A passing verification command is evidence that the command passed. It is not a
browser, API, database, or production smoke test unless the command is one.

## Documentation

| Document | Contents |
|----------|----------|
| [docs/configuration.md](docs/configuration.md) | Every `.sisyphusfy.toml` field: type, default, precedence, safety |
| [docs/adapters.md](docs/adapters.md) | `AgentAdapter` protocol, registry, command construction, model fallback, failure classification, workflow adapters |
| [docs/examples.md](docs/examples.md) | Minimal end-to-end setups for Python, Rust, JavaScript, Flutter, and .NET |
| [docs/ci.md](docs/ci.md) | Continuous-integration usage and JSON result consumption |
| [docs/security.md](docs/security.md) | Command-execution model and review checklist |
| [docs/deployment.md](docs/deployment.md) | GitHub Pages and custom domain setup |

## Quick start: durable loop

The loop starts a fresh agent process for every iteration. The task file and
handoff file are the durable state; previous agent conversation history is not
restored.

For a Markdown checklist:

```bash
sisyphusfy loop \
  --task-path TASKS.md \
  --handoff-path HANDOFF.md \
  --completion-strategy markdown \
  --adapter opencode \
  --model-chain mimo-v2.5 minimax-3 \
  --agent-timeout 2700 \
  --max-iterations 20 \
  --verification-command pytest
```

Use CodeBuddy instead:

```bash
sisyphusfy loop \
  --task-path TASKS.md \
  --handoff-path HANDOFF.md \
  --completion-strategy markdown \
  --adapter codebuddy \
  --model-chain minimax-3
```

For an OpenSpec change, point the workflow adapter at the change directory:

```bash
sisyphusfy loop \
  --task-path openspec/changes/my-change/tasks.md \
  --handoff-path HANDOFF.md \
  --workflow-type openspec \
  --workflow-change-dir openspec/changes/my-change \
  --workflow-validation-command openspec validate my-change --strict \
  --adapter opencode \
  --model-chain mimo-v2.5 minimax-3
```

The default prompt is intentionally short. It asks the agent to read the
configured task and handoff files, implement one task, update state, and stop
when blocked. Override it with `--prompt-template` when a project needs a
different instruction contract.

## Dry-run and machine output

Preview a single command without executing it:

```bash
sisyphusfy --dry-run -- echo "hello world"
```

Preview the loop and hooks:

```bash
sisyphusfy loop --dry-run \
  --task-path TASKS.md \
  --completion-strategy markdown \
  --adapter opencode \
  --model-chain mimo-v2.5
```

Use `--json` for automation and CI consumers.

## Optional completion hooks

Archive and commit hooks are disabled by default. Enable them only after
verification, and always provide an explicit commit allowlist:

```bash
sisyphusfy loop \
  --task-path openspec/changes/my-change/tasks.md \
  --workflow-type openspec \
  --workflow-change-dir openspec/changes/my-change \
  --workflow-validation-command openspec validate my-change --strict \
  --adapter opencode \
  --archive-command openspec archive my-change -y \
  --commit-command git commit -m "feat: complete my change" \
  --commit-allowed-files src README.md
```

Review the dry-run output before enabling these hooks. Sisyphusfy does not
provide automatic push support.

## Programmatic usage

```python
from sisyphusfy.runner import run_agent
from sisyphusfy.result import Classification

result = run_agent(
    ["python3", "script.py"],
    working_directory="/path/to/project",
    prompt="do the thing",
    timeout=30.0,
    env={"API_KEY": "abc123"},
)

if result.classification == Classification.SUCCESS:
    print("Done:", result.stdout)
else:
    print("Failed:", result.classification.value)
```

## Development

Development is tracked with OpenSpec. See `openspec/changes/` for active work and `openspec/specs/` for accepted capability specifications.

```bash
openspec list
openspec list
openspec validate --all --strict
```

The repository is initialized for both OpenCode and CodeBuddy workflows. Those integrations are development conveniences; the product itself remains agent-neutral.

## Supported release targets

Installers download a prebuilt archive that matches the host platform and
architecture. The published set is the same set CI builds, and every target is
built on a runner whose native architecture matches the artifact label.

| Platform | Architecture | CI runner |
|----------|--------------|-----------|
| linux | x86_64 | `ubuntu-latest` |
| darwin | x86_64 | `macos-15-intel` |
| darwin | aarch64 | `macos-14` |
| win32 | x86_64 | `windows-latest` |

`linux/aarch64` is deferred: it is not published because no runner in the
current matrix produces it natively. Install with `pip install sisyphusfy` on
that platform. The installer refuses a deferred target instead of downloading a
mislabeled binary.

## Status

This repository contains the product design, roadmap, core implementation, and
OpenSpec history. The runner, loop engine, agent adapters, workflow
integrations, and completion hooks are implemented and tested.

### Implemented capabilities

- Fresh agent sessions with no conversation history carry-over.
- Durable iteration loop with configurable completion, verification, and timeout.
- OpenCode adapter (`opencode run --model <model>`), CodeBuddy adapter (`codebuddy -p`), and generic command adapter.
- Model-chain fallback with retryable/non-retryable failure classification.
- Workflow adapters: Markdown checklists, JSON predicates, external commands, OpenSpec tasks.
- Configurable blocked-signal detection across stdout and stderr.
- Opt-in archive and commit hooks with explicit file allowlists.
- Default token-efficient prompt when no custom template is configured.
- Human-friendly CLI: `init`, `run`, `resume`, `status`, `doctor` subcommands.
- Project configuration in `.sisyphusfy.toml` with documented precedence.
- Automatic OpenSpec change discovery and task/handoff file detection.
- Human-readable progress, fallback, blocker, and next-action output.

## Name

Sisyphus is the figure from Greek mythology condemned to repeatedly push a boulder uphill. Sisyphusfy turns that image into a practical engineering loop: repeated work is allowed, but durable state makes each attempt advance the project.

## License

Sisyphusfy is released under the [MIT License](LICENSE).
