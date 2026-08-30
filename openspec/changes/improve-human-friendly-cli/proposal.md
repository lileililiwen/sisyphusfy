# Proposal: Improve the Human-Friendly CLI

## Why

The current CLI exposes the runner's internal flags and requires users to know task paths, adapter names, prompt templates, and hook details. This makes the common workflow unnecessarily difficult and undermines the goal of affordable, repeatable fresh-context sessions.

## New

- `init` command for project-local configuration.
- `run <change>` command with automatic workflow discovery.
- `resume`, `status`, and `doctor` commands.
- Human-readable progress, model fallback, blocker, and next-action output.
- Safe explicit flags for dry-run, archive, and commit.
- Configuration defaults with command-line overrides.

## Modified

- Keep the current low-level direct command and loop interfaces as advanced modes.
- Update README examples to show the short common workflow.

## Non-goals

- No new agent provider implementation.
- No automatic push.
- No hidden permission approval.
- No project-language or repository-layout assumption.
- No removal of machine-readable JSON output.
