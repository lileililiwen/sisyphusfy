# Troubleshooting

This document covers failure modes that look like sisyphusfy bugs but are
actually problems in the agent CLI, the verifier, or their configuration.
Sisyphusfy stops and reports these clearly; the fix is in the tool it shells out
to, not in sisyphusfy.

## `UnknownError` / `err_*` from the agent CLI

**Symptom:** the agent step fails and the report shows something like

```text
[agent] error: Unexpected server error. Check server logs for details.
[agent] reference: err_xxxxxxxx
```

and sisyphusfy stops with `stopped: agent_failed`.

**What it means:** this envelope comes from the agent CLI (for opencode, the
`UnknownError` envelope with a `ref` is returned by its provider). It is **not**
a sisyphusfy failure. It means the agent CLI itself could not complete the run —
almost always because *its own* provider or configuration is broken, so it fell
back to a hosted provider that then errored.

**Why it happens:** agent CLIs such as opencode load their provider from your
config. If the configured default model name does not match a provider you
defined, or the provider package is missing, or the config file is corrupted,
the CLI cannot resolve the model and falls back to a built-in hosted provider
that returns the opaque server error above. The `ref` points at the agent CLI's
server logs, which you normally cannot read.

**Diagnose (opencode):**

```bash
opencode run 'hi' --print-logs --log-level DEBUG
```

Inspect the logs for lines such as `ProviderModelNotFoundError: Model not found:
<provider>/<model>. Did you mean: ...?`. The `Did you mean:` hint tells you the
exact model name to use.

**Common fixes:**
- The default `model` in your opencode config must match a model key your
  provider actually registers. Names are case-sensitive: `newapi/MiniMax-M3`
  fails when the provider registers `minimax-m3`.
- If the CLI needs a provider package (e.g. `@ai-sdk/openai-compatible` for
  OpenAI-compatible or Ollama-via-SDK providers), ensure it is installed where
  the CLI loads it from. This is the CLI's prerequisite, not sisyphusfy's.
- Repair a corrupted config file (valid JSON, no stray text appended).

Other agent CLIs print their own diagnostic command via sisyphusfy's
`[agent] diagnose:` line — run it directly to reproduce the failure outside
sisyphusfy.

## Verification never runs after an agent failure

Expected behavior: when the agent exits non-zero, sisyphusfy stops immediately
with `agent_failed` and does **not** run the verifier. This protects you from
trusting output the agent never produced. If you expected verification, the
agent must exit zero first.

## A run stops with `blocked`

**Symptom:** the loop stops with `stopped: blocked` (or `blocked. agent
requested permission or encountered an ambiguity.`) and the report prints a
`blocker:` line taken from the agent's own output.

**What it means:** the agent emitted a configured blocked marker (default:
`NEED_PERMISSION` or `BLOCKED`) in its output, meaning it hit a permission
request or an unresolved choice and deliberately stopped. This is the
agent's signal, not a sisyphusfy error. Blocked detection matches
markers at word boundaries (and on whole stripped lines) rather than
doing a case-insensitive substring search, so ordinary prose such as
"permission bits" or "blocking issue resolved" no longer trips the
blocked path.

**Non-interactive (default for `--json`, pipes, CI):** sisyphusfy stops with
`blocked`, keeps the task/handoff files on disk, and prints the resume command
(`sisyphusfy resume`). It never blocks waiting for input, so automated runs
cannot hang.

**Interactive (a terminal attached, unless `--no-interactive`):** sisyphusfy
pauses, shows the blocker, and asks for a decision:

```text
[sisyphusfy] agent is blocked and needs a decision:
  NEED_PERMISSION: delete file
approve (or type your answer), or 'deny'/'no' to stop:
```

- Approve (empty input, or any free text): the loop re-runs the agent in the
  same iteration with your answer folded into the prompt, then continues past
  the blocker.
- Deny (`deny`/`no`/`n`): the iteration stops with `blocked`, exactly as the
  non-interactive path.
- A privileged or destructive blocker is never auto-approved; it always requires
  your explicit response.

Re-prompts are bounded (default 3 per iteration, `--max-interactive-prompts` on
the low-level `loop` command). If the agent keeps blocking past the cap, the run
stops with `blocked` rather than looping forever. Force a specific mode with
`--interactive` / `--no-interactive`; under `--json` interactive mode is always
off.

## Inspecting diagnostics without rerunning work

`sisyphusfy resume --inspect` reads the most recent diagnostic log
under `<project>/.sisyphusfy/logs/` and prints it without starting a
new agent iteration. The log directory is shared by every component;
files are named after their component (`agent-…`, `verify-…`,
`hook-…`, `workflow-…`) so an agent failure never gets confused with
a verification log. When no log exists, the command reports a clear
"no saved diagnostics" state and returns success.

`--verification-timeout N` on `run` and `resume` overrides the
default 30-second verification limit. The effective value is shown in
both human dry-run output (`verify-timeout: Ns`) and structured
JSON (`verification_timeout: N`) so automation can match what the
verifier actually used.

## The command line in the diagnostic log looks "missing quotes"

Sisyphusfy passes the prompt as a single argument to the subprocess (no shell),
so the command is correct even when the logged line shows it without quotes.
Display rendering quotes multi-word arguments for readability (see
`docs/security.md`); the rendering never changes what executes.
