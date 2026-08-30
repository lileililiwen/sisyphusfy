# Design: Agent Adapters and Model Fallback

## Explore & Reuse

Reuse the archived runner's argument-vector subprocess execution and the durable loop's iteration boundary. Adapter code only translates an agent/model selection into an invocation; it must not own task state or verification.

## Architecture

Define an `AgentAdapter` protocol with `build_command`, `supports_model`, and `classify_failure`. A registry selects adapters by configured name. OpenCode uses a fresh non-continuation invocation; CodeBuddy uses its non-interactive invocation. Model chains are ordered configuration, not constants. Retry only provider/process failures classified as retryable; preserve workspace state between attempts.

## Safety

Credentials come from the environment or agent configuration and are never printed. Permission prompts and ambiguous agent output are blocked outcomes, not retryable provider failures. Tests use fake adapters and commands.
