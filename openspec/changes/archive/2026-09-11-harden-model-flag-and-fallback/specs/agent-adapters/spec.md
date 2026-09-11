# agent-adapters Specification

## ADDED Requirements

### Requirement: Single-owner model injection

The adapter SHALL own model-flag construction for its CLI grammar; the loop SHALL supply only the model value and MUST NOT rewrite `--model`/`-m` arguments by index. Command construction for any model MUST be crash-free, including commands whose last argument is a flag.

#### Scenario: Trailing flag does not crash

- **WHEN** the resolved command ends in `--model` and a fallback model applies
- **THEN** the system MUST NOT raise `IndexError` and MUST produce a runnable command or a clean command-not-found/failure result

#### Scenario: Generic command without opt-in stays flag-free

- **WHEN** a generic command has not opted into model flags and a model is active
- **THEN** the command MUST NOT gain a `--model` argument and the model MUST still be delivered via the `AGENT_MODEL` environment variable

### Requirement: Skipped-model accounting

`try_fallback` SHALL record models rejected by `supports_model` as skips, include them in the attempts trail, and raise exhaustion with an explicit no-attempt state when every model was skipped.

#### Scenario: All models skipped

- **WHEN** every model in the chain is rejected by `supports_model`
- **THEN** the system MUST stop cleanly with the skip list recorded and MUST NOT fail while handling missing run evidence

#### Scenario: Mixed chain audit trail

- **WHEN** a chain contains both skipped and attempted models
- **THEN** `model_attempts` MUST reflect every model considered, in order, with skips distinguished
