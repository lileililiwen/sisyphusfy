# Tasks: Agent Adapters and Model Fallback

## 1. Testing

- [x] Test adapter registry selection and unknown-adapter errors.
- [x] Test OpenCode command construction without continuation flags.
- [x] Test CodeBuddy command construction through a fake executable.
- [x] Test ordered model fallback and workspace preservation.
- [x] Test retryable versus non-retryable failure classification.
- [x] Test credential redaction in logs and JSON results.

## 2. Implementation

- [x] Define the adapter protocol and registry.
- [x] Implement generic configured-command adapter.
- [x] Implement OpenCode adapter.
- [x] Implement CodeBuddy adapter.
- [x] Implement model-chain configuration and fallback policy.
- [x] Integrate adapters with the iteration loop.

## 3. Verification

- [x] Run focused tests twice.
- [x] Run lint, compile, and package checks.
- [x] Validate with strict OpenSpec validation.
