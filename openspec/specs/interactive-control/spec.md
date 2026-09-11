# interactive-control Specification

## Purpose
TBD - created by archiving change interactive-control-center. Update Purpose after archive.
## Requirements
### Requirement: ESC pauses at safe points

In an interactive terminal, a lone ESC keypress SHALL set a pending pause that the loop honors at the next safe point (an iteration boundary or inside the blocked prompt), presenting resume / stop / step-once choices. The pause MUST NOT suspend a running subprocess in v1; an ESC arriving mid-invocation takes effect when that invocation returns.

#### Scenario: ESC between iterations pauses

- **WHEN** ESC is pressed while the loop runs interactively
- **THEN** the system MUST pause before the next agent invocation and offer resume, stop, and step-once

#### Scenario: Arrow keys do not pause

- **WHEN** CSI sequences such as arrow keys arrive
- **THEN** the system MUST NOT treat them as a pause request

#### Scenario: Non-interactive ignores keys

- **WHEN** the run uses `--json` or piped input
- **THEN** the system MUST NOT install key handling and MUST NOT block on input

### Requirement: Slash commands in the blocked prompt

The interactive blocked prompt SHALL accept `/models [name]`, `/compact`, `/help`, `/resume`, and `/stop` alongside plain-text answers and approve/deny. Slash input MUST be consumed by the parser and MUST never be folded into the agent prompt.

#### Scenario: List and switch models

- **WHEN** the operator enters `/models` or `/models <name>`
- **THEN** the system MUST list the chain with active/skip marks or switch subsequent invocations to the named supported model and record the switch

#### Scenario: Refuse unsupported model

- **WHEN** the operator requests a model rejected by `supports_model`
- **THEN** the system MUST refuse with the reason and keep the current model

#### Scenario: Compact on demand

- **WHEN** the operator enters `/compact`
- **THEN** the system MUST compact the handoff file, report before/after counts, and render the next prompt from the compacted file

#### Scenario: Unknown slash shows help

- **WHEN** the operator enters an unknown `/` command
- **THEN** the system MUST print help, re-prompt, and MUST NOT forward the input to the agent

#### Scenario: Pause menu shares the parser

- **WHEN** paused via ESC outside the blocked prompt
- **THEN** the same slash commands MUST be available before resume or stop

