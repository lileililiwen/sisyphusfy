# Continuous integration

Sisyphusfy is a supervisor, not a hosted service. CI jobs invoke it the same way
a developer does and read either the exit status or `--json` output.

## Exit status

| Result | Exit code |
|--------|-----------|
| `complete` | `0` |
| anything else (`max_iterations`, `blocked`, `timeout`, `verification_failed`, `command_not_found`, `unchanged_state`, `models_exhausted`, `adapter_error`, `dry_run`) | `1` |

`command_not_found` is returned when a configured agent, verification, or
completion command cannot be executed; the result names the missing command so a
CI log can point at the fix.

## Preview gate: verify configuration without executing

Use `--dry-run` and `--json` to fail a pull request when the resolved
configuration is wrong, before any agent runs:

```yaml
name: sisyphusfy-config

on: [pull_request]

jobs:
  preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Sisyphusfy
        run: pip install sisyphusfy

      - name: Doctor
        run: sisyphusfy doctor --json

      - name: Preview planned run
        run: sisyphusfy run --dry-run --json
```

## Run a change on a schedule

```yaml
name: sisyphusfy-run

on:
  workflow_dispatch:
  schedule:
    - cron: "17 6 * * 1"

permissions:
  contents: write

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Sisyphusfy
        run: pip install sisyphusfy

      - name: Preview
        run: sisyphusfy run --dry-run

      - name: Run
        env:
          AGENT_MODEL: mimo-v2.5
        run: |
          sisyphusfy run \
            --max-iterations 5 \
            --agent-timeout 1200 \
            --json > sisyphusfy-run.json

      - name: Report
        if: always()
        run: cat sisyphusfy-run.json

      - name: Upload result
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sisyphusfy-run
          path: sisyphusfy-run.json
```

## Consume the JSON result

`--json` prints the structured loop result, including the stop reason, iteration
count, and completion-hook status:

```bash
sisyphusfy run --json > result.json
python - <<'PY'
import json, sys
result = json.load(open("result.json"))
print("stop reason:", result["stop_reason"])
print("iterations:", result["iterations"])
sys.exit(0 if result["stop_reason"] == "complete" else 1)
PY
```

## Notes for CI

- Provide credentials through the environment or the agent's own configuration.
  Sisyphusfy never prints them and never writes them to the task or handoff
  files.
- Run from the repository root, or pass `--project-dir` explicitly. Every
  subprocess, including verification and hooks, uses that directory.
- Keep `--max-iterations` and `--agent-timeout` bounded so a stalled agent cannot
  hold a runner.
- Leave archive and commit hooks disabled unless the job also commits safely;
  they are opt-in and never push. See [security.md](security.md).
