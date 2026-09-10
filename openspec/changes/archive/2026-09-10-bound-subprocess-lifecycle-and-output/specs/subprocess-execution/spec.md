# Subprocess execution Specification

## ADDED Requirements

### Requirement: Bound captured output

Every managed subprocess MUST enforce a configurable bound on in-memory
stdout/stderr while preserving complete output in an explicitly local diagnostic
record when diagnostics are enabled.

#### Scenario: Noisy command runs

- **WHEN** an agent or verifier emits more output than the configured memory bound
- **THEN** the structured result MUST indicate truncation, remain bounded, and the process MUST continue to be classified by exit status

### Requirement: Clean up process descendants

Managed subprocesses MUST be launched in an isolated process group/session where
the platform supports it, and timeout or interruption MUST terminate descendants
within bounded cleanup grace periods.

#### Scenario: Verification spawns a long-lived child

- **WHEN** verification times out after spawning a child
- **THEN** Sisyphusfy MUST attempt to terminate the child group before returning a timeout result

### Requirement: Preserve structured lifecycle outcomes

The execution boundary MUST distinguish success, non-zero failure, timeout,
interrupt, and command-not-found outcomes without raising an unstructured
exception to the caller.

#### Scenario: Executable is missing

- **WHEN** a configured managed command cannot be started
- **THEN** the caller MUST receive a command-not-found result with the attempted command and actionable diagnostic text

### Requirement: Keep progress responsive

Managed commands MUST continue to emit output lines and bounded idle heartbeats
to human progress sinks without mixing progress into JSON stdout.

#### Scenario: Long silent build

- **WHEN** a command produces no output before the heartbeat interval
- **THEN** human mode MUST show elapsed and idle durations while JSON mode remains machine-readable
