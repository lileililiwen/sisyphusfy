# Proposal: Add Optional Archive and Commit Hooks

## Why

A completed workflow may need to archive its specification and record a Git commit, but these operations change durable project state and are not safe defaults. They belong behind explicit, auditable hooks.

## New

- Optional completion hooks for OpenSpec archive and Git commit.
- Dry-run and confirmation controls.
- Clean-worktree and verification preconditions.
- Structured hook results and failure handling.

## Non-goals

- No automatic push.
- No destructive reset, checkout, or cleanup.
- No commit of unrelated changes.
- No assumption that every project uses Git or OpenSpec.
