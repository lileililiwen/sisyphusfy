# safety-and-observability Specification

## Purpose
Bounded subprocess cleanup, commit-hook index safety, and read-only Git inspection so the supervisor reaps descendants, refuses to commit unrelated staged files, and surfaces repository state without ever writing to the workspace.
## Requirements
### Requirement: Bounded subprocess cleanup

The runner MUST launch bounded agent and verification subprocesses so that a
timeout or interrupt attempts to terminate the launched process and its
descendants, then MUST preserve the existing structured timeout/interrupted
classification.

#### Scenario: Agent descendant is stopped on timeout
- **GIVEN** an agent launches a child that remains alive after the agent exits
- **WHEN** the agent timeout expires
- **THEN** the runner attempts group cleanup, reaps the launched process, and
  returns `timeout` without waiting indefinitely for the descendant

### Requirement: Commit allowlist protects the existing index

The commit hook MUST refuse to run when pre-existing staged paths are outside
the canonicalized `commit_allowed_files` set. It MUST apply bounded execution
and fail when its staging command cannot complete successfully.

#### Scenario: Unrelated staged file is rejected
- **GIVEN** one unrelated path is already staged before the hook starts
- **WHEN** the commit hook is invoked with an allowlist excluding that path
- **THEN** the hook returns failure and does not run the commit command

#### Scenario: Staging failure is reported
- **GIVEN** an allowed path cannot be staged successfully
- **WHEN** the commit hook prepares the index
- **THEN** the hook returns failure with the staging command's error and does
  not run the commit command

### Requirement: Read-only Git inspection

The system MUST provide read-only Git status and diff inspection in the selected
project directory, with bounded commands and bounded diff output. The result
MUST identify unavailable Git/repository state without raising an unhandled
exception.

#### Scenario: Human status includes repository summary when requested
- **GIVEN** the selected directory is a Git repository with modified files
- **WHEN** the operator runs `sisyphusfy status --diff`
- **THEN** the output shows branch/status information and changed-file counts

#### Scenario: Diff command returns bounded patch data
- **GIVEN** a repository has a diff larger than the configured display limit
- **WHEN** the operator runs `sisyphusfy diff --json`
- **THEN** the result contains a truncated diff, file/stat metadata, and an
  explicit truncation indicator

#### Scenario: Non-Git directory is structured
- **GIVEN** the selected directory is not a Git repository
- **WHEN** the operator requests status or diff inspection
- **THEN** the command reports repository inspection as unavailable without
  attempting a write

