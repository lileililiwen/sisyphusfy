# Sisyphusfy Design

## Goal

Provide a small external supervisor that repeatedly invokes disposable AI-agent sessions while preserving only deliberate workspace state. The tool must remain useful when the agent, model provider, programming language, repository layout, or task format changes.

## Non-goals

- Sisyphusfy is not an AI model, prompt marketplace, or replacement for an agent CLI.
- It does not define a universal project structure.
- It does not infer product requirements from vague prompts.
- It does not silently approve dangerous commands.
- It does not automatically commit, archive, or push by default.

## Components

### Loop engine

Owns iteration limits, process lifecycle, timeouts, result classification, model fallback, and stop conditions.

### Agent adapter

Describes how to start one agent session, select a model, provide a prompt, capture output, and interpret exit status. The engine must not contain OpenCode- or CodeBuddy-specific assumptions.

### State adapter

Reads task progress and determines whether work remains. Initial strategies may include Markdown checkboxes, JSON predicates, and an external command. OpenSpec is one integration example.

### Verification adapter

Runs a configured command in the project workspace. Verification failure is visible to the next session but is not automatically treated as a model/provider failure.

### Handoff protocol

The agent receives a short generic prompt and is instructed to update a configured handoff file. The runner checks that the file or task state changed, but does not attempt to generate the handoff itself.

## Iteration state machine

```text
READY → RUNNING → VERIFYING → CONTINUE
                    ├────────→ COMPLETE
                    ├────────→ BLOCKED
                    └────────→ FAILED
```

Retrying with another model is allowed only for classified provider/process failures. A test failure, ambiguous requirement, or permission request should remain visible as a task/blocker rather than being hidden by model rotation.

## Token-efficiency rules

- Start a fresh conversation for each attempt unless continuation is explicitly requested.
- Do not paste previous conversation output into a new prompt.
- Ask the agent to read only configured root documents and the active task.
- Limit an iteration to one task or a configured small batch.
- Keep handoff files as summaries, not append-only logs.
- Do not ask the agent to restate the whole repository or specification.
- Start the next specification with a new session and a new handoff boundary.
- Record a documented provider-neutral estimate of every prompt and expose it
  in the structured result; a configured input budget may reject or
  truncate an over-budget prompt before the agent is invoked.

## Safety rules

- Every external command is displayed in dry-run mode.
- Timeouts are mandatory for agent and verification processes.
- Permission prompts do not receive guessed answers.
- Destructive or privileged operations require explicit project/agent configuration.
- Model fallback never bypasses verification.
- Automatic commit, archive, and push are opt-in.
- Configured paths (`task_path`, `handoff_path`, workflow paths) must resolve
  inside the selected project directory; an escape raises a structured
  `ConfigurationError` before the agent is invoked.

## Configuration boundary

Configuration may be supplied through CLI flags, a project file such as `.sisyphusfy.yaml`, or a user-level default. A missing project configuration must produce a useful generic mode rather than assume OpenSpec or a programming language.
