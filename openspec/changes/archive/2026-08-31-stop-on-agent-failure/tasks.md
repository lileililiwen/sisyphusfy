## 1. Testing

- [x] 1.1 Add loop tests proving a non-zero agent exit with `model_chain = []` stops as `agent_failed` and never runs the verifier.
- [x] 1.2 Add tests proving `blocked`, `timeout`, `interrupted`, and `command_not_found` keep priority over `agent_failed`.
- [x] 1.3 Add adapter tests for `parse_error`: envelope on stdout and stderr, no match, malformed JSON, braces inside strings, all built-ins.
- [x] 1.4 Add human-output tests for the agent-failure report, the JSON shape, and `--verbose` agent diagnostics.
- [x] 1.5 Update the two tests that encoded the old behavior and add `parse_error` to the documented protocol methods.

## 2. Stop on agent failure

- [x] 2.1 Add the `agent_failed` stop reason and stop on any non-zero agent exit before verification.
- [x] 2.2 Map a non-retryable model-chain failure to `agent_failed`, reserving `models_exhausted` for all-retryable chains.
- [x] 2.3 Add `parse_error` to the adapter protocol and recover the error name, message, and reference from agent output.
- [x] 2.4 Persist the agent error and the failed run's bounded evidence in the loop result and JSON.

## 3. Reporting and documentation

- [x] 3.1 Print the failing command, exit status, error, reference, diagnostics path, and resume instruction.
- [x] 3.2 Show agent diagnostics for `--verbose` when no verification evidence exists.
- [x] 3.3 Update README and `docs/adapters.md`, `docs/ci.md`, and `docs/security.md`.
- [x] 3.4 Run focused tests, the full suite, lint/compile checks, and strict OpenSpec validation.
