# Configuration

Sisyphusfy reads configuration from four sources and never guesses: a value is
either set explicitly or it keeps its built-in default.

## Precedence

Later sources override earlier ones. `None`-valued entries are ignored, so a
missing key never erases a value from a lower-precedence source.

| Order | Source | Location |
|-------|--------|----------|
| 1 (lowest) | built-in defaults | `sisyphusfy.config.DEFAULT_CONFIG` |
| 2 | user defaults | `~/.config/sisyphusfy/config.toml` |
| 3 | project config | `<project_dir>/.sisyphusfy.toml` |
| 4 (highest) | CLI flags | `sisyphusfy run|resume --adapter ... --model-chain ...` |

`--project-dir` (or `-d`) selects the directory whose `.sisyphusfy.toml` is read
**and** the working directory used for every subprocess the loop starts.

Invalid or unreadable TOML is treated as an empty file, so a broken user
configuration never blocks a project run.

## `.sisyphusfy.toml` fields

Every field below is accepted in both the project file and the user defaults
file.

| Field | Type | Default | Purpose | Safety |
|-------|------|---------|---------|--------|
| `adapter` | string | `"opencode"` | Agent adapter name or executable. Built-in names: `opencode`, `codebuddy`, `generic`. | Executed as a subprocess. Review the binary before use. |
| `model_chain` | list of strings | `[]` | Ordered models tried in sequence. The first retryable provider failure moves to the next model. | Model names are passed through to the adapter, never interpreted by a shell. |
| `workflow_type` | string | `"markdown"` | Workflow state adapter: `markdown`, `json`, `external`, `openspec`. | `external` and `openspec` can run commands. |
| `agent_timeout` | float (seconds) | `60.0` | Timeout for one agent process. | Bounds a single iteration; exceeded runs stop with `timeout`. |
| `max_iterations` | integer | `10` | Maximum productive iterations before the loop stops. | Bounds total work. |
| `verification_command` | list of strings | `[]` | Command run once per productive iteration. Empty disables verification. | Executed as a subprocess. The runner's only independent check of the agent's claims. |
| `verification_timeout` | float (seconds) | `30.0` | Timeout for the verification command. | Bounds verification; exceeded runs stop with `timeout`. |
| `handoff_path` | string | `"HANDOFF.md"` | Handoff file inside the project directory. Discovery falls back to `HANDOFF.md` then `handoff.md`. | Read and written by the agent; keep it free of secrets. |
| `archive_enabled` | boolean | `false` | Enable the archive completion hook. | Opt-in. Runs `openspec archive` after completion and verification succeed. |
| `commit_enabled` | boolean | `false` | Enable the commit completion hook. | Opt-in. Requires `commit_allowed_files`; without it the hook is skipped. |
| `commit_allowed_files` | list of path globs | `[]` | Files the commit hook may stage. | Paths are canonicalized and must resolve inside the project directory; escapes are rejected. |

Task files are discovered, not configured: `tasks.md`, `TASKS.md`, `task.md`, or
`TASK.md` in the project directory, or `openspec/changes/<change>/tasks.md` for a
named change.

When no `verification_command` is configured, Sisyphusfy auto-detects `pytest`,
`make test`, or `cargo test` if the first word is on `PATH`. Auto-detection is a
convenience, not a contract: configure verification explicitly for a release
gate.

## Example

```toml
adapter = "opencode"
model_chain = ["mimo-v2.5", "minimax-3"]
workflow_type = "openspec"
agent_timeout = 2700.0
max_iterations = 20
verification_command = ["pytest", "-q"]
verification_timeout = 600.0
handoff_path = "HANDOFF.md"
archive_enabled = false
commit_enabled = false
commit_allowed_files = []
```

## Commands that receive configuration values

Values reach subprocesses as argument lists, never as shell strings. There is
no interpolation step, so a configuration value cannot inject additional
commands. See [security.md](security.md) for the full execution model.
