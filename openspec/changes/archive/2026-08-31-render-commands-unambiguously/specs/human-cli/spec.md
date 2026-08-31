# human-cli Specification

## ADDED Requirements

### Requirement: Render commands with unambiguous quoting

The CLI MUST render every command it displays (diagnostic logs, the human-readable
result, `doctor`, and dry-run) using shell-style quoting so that a multi-word
argument appears as one quoted token. A command whose arguments are all single
words MUST render unchanged. Command execution MUST remain an argument list passed
to the subprocess runner without a shell, and structured JSON output MUST keep
`command` as a list.

#### Scenario: Agent command with a long prompt

- **WHEN** the agent command is shown and its prompt is passed as a single multi-word argument
- **THEN** the displayed command MUST quote that argument so its boundaries are visible, rather than space-joining it into several arguments

#### Scenario: Simple verification command

- **WHEN** a command of single-word arguments such as `dotnet test App.sln` is shown
- **THEN** the CLI MUST display it unchanged, with no added quotes

#### Scenario: Structured output

- **WHEN** the result is emitted as JSON
- **THEN** the `command` field MUST remain a list of strings, never a quoted string
