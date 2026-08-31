# supervisor-quality Specification

## ADDED Requirements

### Requirement: Show live subprocess progress

Human-facing loop commands MUST show line-oriented progress while an agent or
verification subprocess is running and MUST emit a periodic heartbeat when no
new output is received. Progress MUST identify the component as `agent` or
`verify`.

#### Scenario: Verification produces output

- **WHEN** a verification subprocess writes a line
- **THEN** the human CLI MUST display that line with a `verify` component label
  while the subprocess continues running

#### Scenario: Verification is quiet

- **WHEN** verification produces no output for the heartbeat interval
- **THEN** the human CLI MUST display a `verify` heartbeat with elapsed time

### Requirement: Label elapsed time with explicit units

Every human-facing elapsed-time and timeout value MUST include explicit units.
Durations under one minute MUST use `Ns`; durations of one minute or more MUST
use `Nm Ns`. The CLI MUST NOT print a bare number or unitless clock value.

#### Scenario: Short duration

- **WHEN** elapsed time is 42 seconds
- **THEN** the CLI MUST display `42s`

#### Scenario: Long duration

- **WHEN** elapsed time is 72 seconds
- **THEN** the CLI MUST display `1m 12s`

#### Scenario: Timeout

- **WHEN** a subprocess reaches its configured timeout
- **THEN** the timeout message MUST include the limit with explicit units, such
  as `timeout after 600s`

### Requirement: Report timeout diagnostics immediately

When a subprocess times out, the human CLI MUST immediately report the
component, timeout duration, available partial output, and diagnostic log path.

#### Scenario: Verification times out during a build

- **WHEN** verification is terminated by its timeout
- **THEN** the CLI MUST print the timeout summary and log path without requiring
  another loop iteration

### Requirement: Interrupt safely

Ctrl-C during an agent or verification subprocess MUST produce a structured
interrupted result, preserve task and handoff state, and prevent archive and
commit hooks from running.

#### Scenario: User interrupts a running verification

- **WHEN** the user presses Ctrl-C while verification is running
- **THEN** Sisyphusfy MUST stop the child, preserve durable state, report the
  interruption, and skip completion hooks
