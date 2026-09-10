# Proposal: Harden agent adapter and fallback contracts

## Why

Model fallback is a central reliability feature, but its current classification
path inspects only stderr while structured agent errors are parsed from both
streams. The generic adapter also risks appending configured arguments twice.
These defects can waste provider calls and make valid adapters fail in opaque
ways.

## Scope

- Classify retryable failures from bounded combined agent output.
- Ensure generic and named adapters produce exactly one command shape per
  attempt.
- Preserve fresh invocation and model-selection guarantees.
- Add adapter-contract and fallback regression tests.

## Non-goals

- No provider-specific API client or tokenizer.
- No automatic retry of task-level failures.
- No conversation/session continuation.
- No changes to verification or completion policy.

This belongs at the adapter boundary because the loop must remain independent
of agent CLIs and model providers.
