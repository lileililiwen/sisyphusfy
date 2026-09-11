# iteration-loop Specification

## ADDED Requirements

### Requirement: Loop delegates model flags to adapters

The iteration loop SHALL NOT perform `--model`/`-m` argument surgery on adapter-built commands; it SHALL pass the active model to the adapter and invoke the returned command unchanged.

#### Scenario: Adapter-built command passes through

- **WHEN** an adapter builds a command for a fallback model
- **THEN** the loop MUST invoke that command without rewriting its model arguments
