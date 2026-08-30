# Sisyphusfy

Fresh agent sessions. Persistent project progress.

Sisyphusfy is a project-agnostic runner for executing software tasks through disposable AI-agent sessions. It keeps durable state in project files, supports multiple agent CLIs and model fallback, and avoids carrying an expensive conversation history from one task or specification to the next.

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

## Future usage (planned)

The `run` subcommand with agent adapters, model chains, and verification hooks is planned for a subsequent change. The minimal runner currently supports direct command execution only.

## Quick start

Install and run:

```bash
pip install -e .
sisyphusfy --help
```

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
sisyphusfy -p "fix the bug in auth.py" -- opencode run
```

Set working directory and environment variables:

```bash
sisyphusfy -d /path/to/project -t 60 -e API_KEY=abc123 -e DEBUG=1 -- my-agent
```

Programmatic usage:

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
openspec status --change implement-minimal-runner
openspec validate implement-minimal-runner --strict
```

The repository is initialized for both OpenCode and CodeBuddy workflows. Those integrations are development conveniences; the product itself remains agent-neutral.

## Status

This repository contains the product design, roadmap, and core implementation. The runner, loop engine, agent adapters, workflow integrations, and completion hooks are implemented and tested.

### Implemented capabilities

- Fresh agent sessions with no conversation history carry-over.
- Durable iteration loop with configurable completion, verification, and timeout.
- OpenCode adapter (`opencode run --model <model>`), CodeBuddy adapter (`codebuddy -p`), and generic command adapter.
- Model-chain fallback with retryable/non-retryable failure classification.
- Workflow adapters: Markdown checklists, JSON predicates, external commands, OpenSpec tasks.
- Configurable blocked-signal detection across stdout and stderr.
- Opt-in archive and commit hooks with explicit file allowlists.
- Default token-efficient prompt when no custom template is configured.

## Name

Sisyphus is the figure from Greek mythology condemned to repeatedly push a boulder uphill. Sisyphusfy turns that image into a practical engineering loop: repeated work is allowed, but durable state makes each attempt advance the project.

## License

Sisyphusfy is released under the [MIT License](LICENSE).
