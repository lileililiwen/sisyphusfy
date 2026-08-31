# supervisor-quality Specification Deltas

## ADDED Requirements

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
