# Design: Optional Archive and Commit Hooks

## Explore & Reuse

Reuse the workflow integration completion result and the existing subprocess runner. Hooks are external commands with explicit configuration; the core does not embed Git or OpenSpec libraries.

## Architecture

A completion pipeline runs only after task completion and verification success. Each hook declares a command, working directory, allowed files, and whether confirmation is required. The Git hook stages an explicit allowlist or generated paths, never the whole workspace. Archive and commit failures stop the pipeline with their original evidence.

## Safety

Hooks are disabled by default. Dry-run prints every command. Push is excluded from this change. Tests use fake Git/OpenSpec commands and prove unrelated files are not staged.
