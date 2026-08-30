# Proposal: Add Agent Adapters and Model Fallback

## Why

The generic loop must work with different agent CLIs and recover from provider quota exhaustion without restoring the expensive previous conversation. This change adds an adapter protocol and ordered fallback attempts.

## New

- Agent adapter interface for command construction and prompt delivery.
- Configurable OpenCode and CodeBuddy adapters.
- Ordered model chain and retryable provider/process failure policy.
- Safe handling for unknown agents and exhausted model chains.

## Non-goals

- No task-state parsing or verification loop changes.
- No automatic permission approval.
- No provider API implementation inside Sisyphusfy.
- No hardcoded model names or credentials.
