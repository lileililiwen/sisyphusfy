# supervisor-quality Specification

## Purpose

Guarantee that the supervisor's own control flow is trustworthy: dry-run has no
side effects, verification is the single source of completion evidence and runs
at most once per iteration before hooks, the selected project directory is
honored at every subprocess boundary, only artifacts CI can actually build are
published, long-running subprocesses report live progress with explicit timing
and interrupt safely, and the public configuration, adapter, and
command-execution contracts are documented.
## Requirements
### Requirement: Keep dry-run non-executing at every boundary

The supervisor MUST NOT execute an agent, verification command, external completion check, workflow validation command, archive hook, or commit hook when dry-run is enabled.

#### Scenario: External completion check in dry-run

- **WHEN** a loop uses an external completion strategy with dry-run enabled
- **THEN** the completion check MUST NOT execute and the result MUST identify the planned dry-run behavior

#### Scenario: Workflow validation in dry-run

- **WHEN** an OpenSpec or other workflow adapter has a validation command and dry-run is enabled
- **THEN** the validation command MUST NOT execute

### Requirement: Verify exactly once before accepting completion

The supervisor MUST run configured verification at most once for each productive iteration and MUST complete verification before invoking completion hooks or returning a complete result.

#### Scenario: Incomplete iteration

- **WHEN** an agent makes progress but leaves work incomplete
- **THEN** the configured verification command MUST run no more than once for that iteration

#### Scenario: Initially complete state

- **WHEN** task or workflow state is already complete and verification is configured
- **THEN** verification MUST succeed before archive or commit hooks run

#### Scenario: Failing verification

- **WHEN** verification fails
- **THEN** the supervisor MUST return verification failure and MUST NOT invoke completion hooks

### Requirement: Respect the selected project directory

High-level commands MUST use the selected project directory as the working directory for agents, verification, workflow commands, archive hooks, and commit hooks, and MUST resolve relative state paths consistently against that directory.

#### Scenario: Run from outside the project

- **WHEN** a user invokes a high-level command with `--project-dir /path/to/project` from another directory
- **THEN** every subprocess MUST execute against `/path/to/project`

#### Scenario: Relative hook paths

- **WHEN** a configured hook or workflow command uses relative paths
- **THEN** those paths MUST be interpreted relative to the selected project directory

### Requirement: Publish only truthful release targets

Release metadata, installers, npm platform detection, and CI MUST expose the same platform/architecture set, and CI MUST NOT label a binary with an architecture different from the binary it built.

#### Scenario: Unsupported target

- **WHEN** a target cannot be built for its advertised architecture
- **THEN** the target MUST be omitted or built with a verified native/cross-compilation process, and installers MUST not advertise it as available

### Requirement: Document public extension and execution contracts

The repository MUST document the public TOML configuration schema, agent adapter protocol, CI usage, supported ecosystem examples, and security implications of user-controlled command execution.

#### Scenario: Configure a project

- **WHEN** a user reads the configuration documentation
- **THEN** the user MUST find each supported field, type, default, precedence rule, and safety gate

#### Scenario: Author an adapter

- **WHEN** a user wants to add an agent adapter
- **THEN** the user MUST find the required protocol methods, registration path, command-input rules, model behavior, and failure classification contract

#### Scenario: Review command execution risk

- **WHEN** a user enables an agent, verification, workflow, archive, or commit command
- **THEN** documentation MUST identify that the command is executable user-controlled input and explain timeout, working-directory, dry-run, and commit-allowlist safeguards

### Requirement: Run completion checks in the selected working directory

The supervisor MUST run a completion check command in the same working directory it uses for agents, verification, workflow validation, and completion hooks, unless the check declares its own directory.

#### Scenario: Low-level loop with a selected directory

- **WHEN** a low-level loop runs with `-d /path/to/project` and an external completion strategy
- **THEN** the completion check command MUST execute in `/path/to/project`

#### Scenario: Explicit completion check directory

- **WHEN** a completion strategy is constructed with its own working directory
- **THEN** the supervisor MUST use that directory instead of the loop working directory

### Requirement: Report missing commands as structured failures

The supervisor MUST report a missing agent, verification, or completion-check executable as a `command_not_found` result that names the command instead of raising an unhandled exception.

#### Scenario: Missing agent command

- **WHEN** the configured agent executable does not exist
- **THEN** the run result MUST be classified `command_not_found` and the loop MUST stop with an actionable message naming the command

#### Scenario: Missing verification command

- **WHEN** the configured verification executable does not exist
- **THEN** the loop MUST stop with `command_not_found` and MUST NOT invoke completion hooks

#### Scenario: Missing completion check command

- **WHEN** an external completion check or workflow command does not exist
- **THEN** the loop MUST stop with `command_not_found` and MUST NOT invoke completion hooks

### Requirement: Resolve verification commands from project evidence

When verification is not explicitly configured, the supervisor MUST resolve a
command using deterministic project markers and executable availability. A
detector MUST validate the required project input before selecting a command;
the presence of an executable alone MUST NOT select a verifier. Explicitly
configured verification MUST take precedence over all discovery.

#### Scenario: Discover a .NET verifier

- **GIVEN** a project contains an `.sln` or `.csproj` file and `dotnet` is
  available
- **WHEN** verification is not configured
- **THEN** the resolved verifier MUST be `dotnet test` against the discovered
  solution or project input

#### Scenario: Do not select an unrelated Make verifier

- **GIVEN** `make` is available but the project has no Makefile declaring a
  `test` target
- **WHEN** verification is not configured
- **THEN** discovery MUST NOT select `make test`

#### Scenario: Explicit verifier wins

- **GIVEN** a user configures a non-empty verification command
- **WHEN** a loop is started
- **THEN** the supervisor MUST execute that command and MUST NOT replace it
  through auto-detection

### Requirement: Retain verification evidence

The supervisor MUST retain the structured result of each verification
invocation, including command, working directory, exit status, classification,
timeout state, and bounded output metadata, in the loop result.

#### Scenario: Verification fails

- **WHEN** verification exits non-zero
- **THEN** the loop result MUST identify verification failure and include the
  verifier command, exit status, and diagnostic log path

#### Scenario: Verification times out

- **WHEN** verification exceeds its configured timeout
- **THEN** the loop result MUST identify timeout and retain any captured output
  and diagnostic log path

### Requirement: Provide inspectable local diagnostics

After a verification invocation, the supervisor MUST write its stdout and
stderr to a local diagnostic log with bounded retention and MUST report the log
path in human and structured results. The default human result MUST remain
concise and MUST NOT print the full diagnostic streams.

#### Scenario: Concise failed verification output

- **WHEN** verification fails during `sisyphusfy run` or `sisyphusfy resume`
- **THEN** the command MUST print the verifier, failure status, and log path,
  followed by the resume instruction

#### Scenario: Deliberate diagnostic inspection

- **WHEN** the user supplies the documented verbose or log-inspection option
- **THEN** Sisyphusfy MUST display the saved verification diagnostics for the
  relevant run

### Requirement: Explain the resolved verifier

`sisyphusfy doctor` and dry-run output MUST identify whether verification is
configured or discovered and MUST show the resolved command, or clearly report
that no verifier was found.

#### Scenario: Doctor diagnoses a project

- **WHEN** the user runs `sisyphusfy doctor`
- **THEN** the output MUST show the verification source and command before the
  loop is executed

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

### Requirement: Retain and report agent failure evidence

When the loop stops because an agent run failed, the supervisor MUST retain the
structured agent evidence, including command, exit status, bounded output
metadata, and diagnostic log path, together with any recovered agent error in
the loop result, and MUST report the failure concisely with the diagnostic path
and the resume instruction.

#### Scenario: Agent fails with a structured error

- **WHEN** an agent exits non-zero and its output carries a recognizable error
- **THEN** the human result MUST print the failing agent command, its exit
  status, the recovered error message, any error reference, and the diagnostic
  log path, followed by the resume instruction

#### Scenario: Agent fails without a structured error

- **WHEN** an agent exits non-zero and no error can be recovered
- **THEN** the human result MUST still print the failing command, its exit
  status, and the diagnostic log path

#### Scenario: Inspect agent diagnostics deliberately

- **WHEN** the user supplies the documented verbose option and the run retains
  no verification evidence
- **THEN** Sisyphusfy MUST display the saved agent diagnostics instead of
  reporting that no diagnostics exist

