# iteration-loop Specification

## ADDED Requirements

### Requirement: No unenforced agent invocation

The iteration loop SHALL NOT invoke the agent with a prompt that has not passed budget preparation when a budget is configured, on any path including blocked-resolution re-runs.

#### Scenario: All paths enforced

- **WHEN** a budget is configured and the loop re-runs the agent after an operator approval
- **THEN** the re-run prompt MUST have a recorded budget event decision and estimate before invocation
