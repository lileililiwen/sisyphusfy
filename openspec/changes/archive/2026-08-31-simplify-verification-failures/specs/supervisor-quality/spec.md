# supervisor-quality Specification

## ADDED Requirements

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
