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
| `verification_command` | list of strings | `[]` | Command run once per productive iteration. Empty hands the choice to marker-based discovery. | Executed as a subprocess. Explicit values always win over discovery; never passed through a shell. |
| `verification_timeout` | float (seconds) | `30.0` | Timeout for the verification command. | Bounds verification; exceeded runs stop with `timeout`. |
| `handoff_path` | string | `"HANDOFF.md"` | Handoff file inside the project directory. Discovery falls back to `HANDOFF.md` then `handoff.md`. | Read and written by the agent; keep it free of secrets. |
| `archive_enabled` | boolean | `false` | Enable the archive completion hook. | Opt-in. Runs `openspec archive` after completion and verification succeed. |
| `commit_enabled` | boolean | `false` | Enable the commit completion hook. | Opt-in. Requires `commit_allowed_files`; without it the hook is skipped. |
| `commit_allowed_files` | list of path globs | `[]` | Files the commit hook may stage. | Paths are canonicalized and must resolve inside the project directory; escapes are rejected. |

Task files are discovered, not configured: `tasks.md`, `TASKS.md`, `task.md`, or
`TASK.md` in the project directory, or `openspec/changes/<change>/tasks.md` for a
named change.

## Verification discovery

When `verification_command` is empty, Sisyphusfy resolves one from project
markers. Detection is read-only: it inspects files and executable availability,
never runs a candidate verifier, and never invokes a shell.

| Order | Ecosystem | Project marker | Executable | Command |
|-------|-----------|----------------|------------|---------|
| 1 | .NET | `*.sln`, else `*.csproj` in the project root | `dotnet` | `dotnet test <marker>` |
| 2 | Rust | `Cargo.toml` | `cargo` | `cargo test` |
| 3 | Python | `pytest.ini`, `pyproject.toml`, `setup.cfg`, `setup.py`, `tox.ini`, or a `tests/` / `test/` directory | `pytest` | `pytest` |
| 4 | JavaScript | `package.json` with a `scripts.test` entry | `npm` | `npm test` |
| 5 | Flutter/Dart | `pubspec.yaml` | `flutter` | `flutter test` |
| 6 | Make | `Makefile`, `makefile`, or `GNUmakefile` declaring a `test:` target | `make` | `make test` |

The first detector whose marker **and** executable are both present wins. A
marker without its executable is skipped, and an executable without its marker
selects nothing: `make` on `PATH` never implies `make test`. If a marker exists
but cannot be read (for example a malformed `package.json`), detection stops
instead of falling through to an unrelated ecosystem.

Markers are read from the project directory only. When no detector matches,
`sisyphusfy doctor` reports that no verifier was found and the loop runs without
verification, so a run never looks like a verified success.

## Verification diagnostics

Each verification invocation writes its complete stdout and stderr to
`<project_dir>/.sisyphusfy/logs/verification-<timestamp>-<pid>-i<iteration>.log`,
keeping the 20 newest files. The logs are local diagnostics: Sisyphusfy never
commits or archives them and records no environment values.

Default human output stays concise — verifier, status, and log path — and JSON
carries bounded metadata (`command`, `source`, `status`, `exit status`, timeout
flag, log path) plus truncated output. Read the full streams with
`sisyphusfy run|resume --verbose`, or open the reported log path.

A passing verification command means that command passed. It is not a browser,
API, database, or production smoke test unless the command you configure is one.

## Repository inspection

`sisyphusfy status --diff` and the dedicated `sisyphusfy diff` subcommand run
a small, read-only Git inspection in the selected project directory. Both
commands execute only `git status`, `git diff`, and `git diff --stat`, each
bounded by a 10-second timeout. Nothing is staged, committed, or pushed.

`sisyphusfy status --diff` adds a `git:` section (branch, changed-file count,
and a short status list) to the existing status output, and JSON gains a
`git` object alongside the existing fields.

`sisyphusfy diff` is the dedicated form and supports:

- `sisyphusfy diff` — show the unified diff for unstaged changes.
- `sisyphusfy diff --staged` — show the staged (`--cached`) diff.
- `sisyphusfy diff --stat` — show per-file change statistics only.
- `sisyphusfy diff --max-bytes N` — cap the diff payload (default 50 KB).
- `sisyphusfy diff --json` — emit a structured result with `diff_text`,
  `stat_text`, `changed_files`, `branch`, and a `truncated` flag.

The unified diff is capped at `--max-bytes` (50 KB by default); when that
limit is exceeded the result carries `truncated: true` and the body ends with
`... (diff truncated)`. Use a larger `--max-bytes`, read the diff via JSON, or
inspect the workspace with the Git CLI directly when you need the full
patch.

A missing `git` executable or a non-repository directory is reported as a
structured unavailable state with a `reason` (`git_unavailable` /
`not_a_repository` / `directory_not_found`) instead of raising an
unhandled exception.

## Interactive blocked resolution

When an agent run reports a blocked marker (see [troubleshooting](troubleshooting.md)),
`sisyphusfy run|resume` can pause and ask you for a decision on a terminal. This
is controlled by the `--interactive` / `--no-interactive` flags:

- Neither flag: auto-detect. Interactive when stdin is a terminal, non-interactive
  otherwise (so piped/CI runs never hang).
- `--interactive`: always prompt for blocked decisions.
- `--no-interactive`: never prompt; stop and report `blocked` (the default for
  `--json`).

The low-level `sisyphusfy loop` command additionally takes
`--max-interactive-prompts N` to bound re-prompts per iteration (default 3).
Denial or an unresolvable blocker always stops the iteration with `blocked`, and
verification and completion hooks never run on a blocked run.

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
