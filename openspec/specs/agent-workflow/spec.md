# agent-workflow Specification

## Purpose
TBD - created by archiving change audit-and-fix-agent-workflow. Update Purpose after archive.
## Requirements
### Requirement: Build valid fresh agent invocations

Each named agent adapter MUST build a valid non-interactive command for its documented CLI and MUST omit conversation continuation identifiers.

#### Scenario: OpenCode invocation

- **WHEN** the OpenCode adapter is configured with a model and prompt
- **THEN** it MUST produce the installed OpenCode `run` command shape with the model and prompt, without `-c` or `-s`

#### Scenario: CodeBuddy invocation

- **WHEN** the CodeBuddy adapter is configured with a model and prompt
- **THEN** it MUST produce the documented non-interactive CodeBuddy command shape and pass the prompt without restoring a prior conversation

### Requirement: Observe current workflow state

Workflow adapters MUST reload configured task/state files for every completion and snapshot observation.

#### Scenario: Task becomes complete

- **WHEN** an agent changes an unchecked task to checked between two observations
- **THEN** the next observation MUST report completion

#### Scenario: JSON state changes

- **WHEN** an agent changes a configured JSON predicate from false to true
- **THEN** the next observation MUST report completion using the new data

### Requirement: Verify before completion hooks

The loop MUST run configured verification before returning complete or invoking completion hooks.

#### Scenario: Completed task with failing verification

- **WHEN** all tasks are complete but verification exits non-zero
- **THEN** the loop MUST return verification failure and MUST NOT invoke archive or commit hooks

#### Scenario: Completed task with successful verification

- **WHEN** all tasks are complete and verification succeeds
- **THEN** the loop MUST return complete and may invoke explicitly enabled hooks

### Requirement: Provide a safe default prompt

The loop MUST provide a concise default prompt when no custom template is configured.

#### Scenario: No custom prompt

- **WHEN** the user starts a loop without a prompt template
- **THEN** the agent MUST receive instructions to read configured state, implement one task, update handoff/state, and stop safely when blocked

### Requirement: Classify blocked agent outcomes

The loop MUST classify configured permission and unresolved-choice signals as blocked without classifying ordinary implementation or verification failures as blocked.

#### Scenario: Permission signal on stdout

- **WHEN** an agent emits a configured permission signal on stdout or structured output
- **THEN** the loop MUST stop with a blocked result

#### Scenario: Ordinary test failure

- **WHEN** an agent exits non-zero with ordinary test failure output and no blocked signal
- **THEN** the loop MUST preserve a failure result rather than classify it as blocked

### Requirement: Enforce commit allowlists

An enabled commit hook MUST stage only explicitly allowed paths and MUST prevent unrelated workspace files from being included.

#### Scenario: Unrelated file is present

- **WHEN** a commit hook runs with an allowlist and an unrelated file exists
- **THEN** the unrelated file MUST remain unstaged and uncommitted

#### Scenario: Allowlist is empty

- **WHEN** commit is enabled without an explicit allowlist
- **THEN** the hook MUST fail safely or require explicit confirmation rather than stage the whole workspace

