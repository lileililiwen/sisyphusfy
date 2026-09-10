# Proposal: Make workspace progress and completion reliable

## Why

The loop treats task/handoff edits as the only evidence of productive work,
uses broad substring blocker detection, accepts paths outside the project
boundary, and handles some checklist/configuration variants inconsistently.
These behaviors can stop after real code work, block on ordinary output, or run
against the wrong files.

## Scope

- Add optional workspace/Git change evidence to progress detection.
- Make blocker detection structured and less prone to false positives.
- Enforce project-relative path boundaries and normalize checklist parsing.
- Surface malformed configuration instead of silently falling back.

## Non-goals

- No automatic commit, staging, or archive.
- No mandatory Git dependency.
- No universal task-file format.
- No change to agent or provider retry policy.

This belongs in workflow and configuration adapters, with Git remaining optional.
