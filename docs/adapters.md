# Agent and workflow adapters

Sisyphusfy keeps agent-specific and task-format-specific behavior out of the
loop engine. Both are protocols with a registry (agents) or a resolver
(workflows).

## The `AgentAdapter` protocol

`sisyphusfy.adapters.AgentAdapter` is a `runtime_checkable` `Protocol` with four
methods:

```python
class AgentAdapter(Protocol):
    def build_command(self, working_directory: str, prompt: str | None = None) -> list[str]: ...
    def supports_model(self, model: str) -> bool: ...
    def classify_failure(self, exit_status: int, stderr: str) -> FailureClass: ...
    def parse_error(self, output: str) -> AgentError | None: ...
```

### `build_command(working_directory, prompt)`

Returns the argument list for one agent process. Rules:

- Return a **list**, never a shell string. Sisyphusfy passes it to
  `subprocess.run` without a shell, so no quoting or interpolation happens.
- Build a **fresh list per call**. The loop starts a new process for every
  iteration and every fallback model; a shared mutable list would leak state
  between sessions.
- The prompt may be passed as an argument or through stdin. The runner always
  sends the prompt on stdin as well, so an adapter that ignores `prompt` still
  works with agents reading stdin.
- `working_directory` is the project directory selected with `--project-dir`. It
  is the process `cwd`; an adapter does not need to `cd` itself.

### `supports_model(model)`

Return `True` when the adapter can forward the model to the agent. Returning
`False` skips the model during fallback instead of failing the chain.

### `classify_failure(exit_status, stderr)`

Map a finished process to a `FailureClass`:

| `FailureClass` | Meaning | Loop behavior |
|----------------|---------|---------------|
| `RETRYABLE_PROVIDER` | Provider-side failure (quota, rate limit, `429`, `502`, `503`, overload, capacity) | Continue with the next model in the chain |
| `RETRYABLE_PROCESS` | Process-level failure (`exit_status == -1` or `> 128`) | Continue with the next model |
| `NON_RETRYABLE` | Task-level failure | Stop with `agent_failed`; the chain is not advanced |

The built-in adapters treat these substrings in `stderr` as provider failures:
`quota`, `rate_limit`, `rate limit`, `429`, `503`, `502`, `provider`,
`overloaded`, `capacity`.

Exhausting every model raises `ModelChainExhausted`, which the loop reports as
`models_exhausted` with the list of attempted models. That result is reserved
for the case where **every** model failed retryably; a single non-retryable
failure stops the iteration as `agent_failed` without trying the next model.

### `parse_error(output)`

Recover a structured error from one finished agent run so the loop can report
it. `output` is the agent's combined stdout and stderr. Return an `AgentError`
with the recovered `name`, `message`, and `reference`, or `None` when the output
carries no recognizable error.

The built-in adapters share `sisyphusfy.adapters.parse_error_envelope`, which
scans for the first balanced JSON object carrying a `name` and reads the message
from `data.message` and the reference from `data.ref`:

```text
Error: {
"name": "UnknownError",
"data": {
"message": "Unexpected server error. Check server logs for details.",
"ref": "err_cbece906"
}
}
```

Rules:

- Parsing is best-effort and MUST NOT raise. Anything unrecognized returns
  `None`; the loop still stops on the exit status and reports the diagnostics.
- Read the whole combined output: agents write errors to either stream and
  often span several lines.
- Return only what the agent actually reported. Do not invent a message.

The loop calls `parse_error` defensively, so an adapter that does not implement
it still works and simply reports no structured error. Because the protocol is
`runtime_checkable`, omitting the method does mean the adapter no longer
satisfies `isinstance(adapter, AgentAdapter)`.

## Built-in adapters

| Name | Command | Model flag |
|------|---------|------------|
| `opencode` | `opencode run [--model <model>] [prompt]` | `--model` |
| `codebuddy` | `codebuddy -p [--model <model>] [prompt]` | `--model` |
| `generic` | the configured command verbatim | none (passes through) |

`AGENT_MODEL` is set in the child environment for every run.

## Model behavior

`model_chain` is an ordered list. For each iteration the loop calls
`build_command` with the current model, then inspects the result:

1. exit status `0` ends the iteration successfully;
2. a non-retryable failure stops the iteration with `agent_failed` and does not
   advance the chain; a retryable failure moves to the next model;
3. a model rejected by `supports_model` is skipped, not failed.

A non-zero exit status always stops the iteration. Verification runs only after
an iteration exits `0`, so a failed agent is never verified.

The `--model` flag is appended only when the adapter reports support and the
command does not already carry `--model` or `-m`; an existing flag is rewritten
in place so a model is never passed twice. Fallback is per iteration: iteration
`n + 1` starts from the first model in `model_chain` again.

## Registering a custom agent adapter

```python
from sisyphusfy.adapters import AdapterRegistry

class MyAgent:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def build_command(self, working_directory: str, prompt: str | None = None) -> list[str]:
        cmd = ["my-agent", "--cwd", working_directory]
        if self.model:
            cmd.extend(["--model", self.model])
        if prompt:
            cmd.append(prompt)
        return cmd

    def supports_model(self, model: str) -> bool:
        return True

    def classify_failure(self, exit_status: int, stderr: str):
        from sisyphusfy.adapters import FailureClass
        if "quota" in stderr.lower():
            return FailureClass.RETRYABLE_PROVIDER
        return FailureClass.NON_RETRYABLE

    def parse_error(self, output: str):
        from sisyphusfy.adapters import parse_error_envelope
        return parse_error_envelope(output)


registry = AdapterRegistry()
registry.register("my-agent", MyAgent)
```

`AdapterRegistry` starts with the built-ins and is passed to
`resolve_adapter(config, agent_command=..., registry=...)`. An unknown adapter
name raises `AdapterError`, which the loop reports as `adapter_error` rather
than guessing a command.

## Workflow adapters

`sisyphusfy.workflows.WorkflowAdapter` tracks task state:

```python
class WorkflowAdapter(Protocol):
    def has_work(self) -> bool: ...
    def is_complete(self) -> bool: ...
    def explain(self) -> str: ...
    def snapshot(self) -> dict[str, str]: ...
    def reload(self) -> None: ...
```

`reload()` is called before every observation so state written by the agent or
by an external tool is picked up.

| Type | `WorkflowConfig` fields | State source |
|------|-------------------------|--------------|
| `markdown` | `task_path` | Checkbox counts in a Markdown file |
| `json` | `state_path`, `predicate` | Nested key, optionally compared (`tasks.done >= 3`) |
| `external` | `check_command`, `timeout` | Exit status of a command |
| `openspec` | `change_dir`, `validation_command`, `timeout` | `tasks.md` checkboxes plus a validation command |

`WorkflowConfig` also carries `working_directory` and `dry_run`. Relative paths
(`task_path`, `state_path`, `change_dir`) resolve against the selected project
directory; commands run in that directory. Under `--dry-run` the loop never
calls an adapter that would execute a subprocess.

Command-driven adapters report themselves through
`adapter_runs_commands(adapter)`. A custom adapter that runs a command should
expose `runs_commands = True` (or a `check_command` / `validation_command`
attribute) so dry-run can skip it honestly instead of reporting a completion
state it did not verify.
