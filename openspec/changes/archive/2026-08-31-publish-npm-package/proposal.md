# Proposal: Publish the npm launcher

## Why

The repository documents `npm install -g sisyphusfy`, but the tagged release
workflow does not publish the `npm/` package. The public npm registry therefore
returns E404 for the documented installation command.

## What Changes

- Add a tokenless npm trusted-publishing job to tagged releases.
- Add regression coverage for the workflow contract.
- Document npmjs.org setup and the one-time v0.1.0 publication.

## Non-goals

- Reimplement the Python runner in JavaScript.
- Add a long-lived npm token to GitHub Actions.
- Change the existing GitHub artifact or PyPI publication behavior.

## Scope

Add npm trusted publishing to the tagged release workflow, test the workflow
contract, and document the one-time npmjs.org trusted-publisher configuration
and the manual publication required for the already-existing v0.1.0 release.
