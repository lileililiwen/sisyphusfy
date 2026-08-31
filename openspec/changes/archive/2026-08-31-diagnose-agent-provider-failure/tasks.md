## 1. Testing

- [x] 1.1 Add tests: `UnknownError` envelope gets the opencode diagnostic hint in the human report and in JSON; a specific error gets none.
- [x] 1.2 Add tests: `OpenCodeAdapter.diagnostic_hint()` returns the opencode command; generic/codebuddy adapters return a generic hint.
- [x] 1.3 Add a test: `AgentError.to_dict()` round-trips the `hint` field only when set.
- [x] 1.4 Add a test: `docs/troubleshooting.md` documents the `UnknownError` diagnosis with the diagnostic command.

## 2. Report provider-side errors with a hint

- [x] 2.1 Add optional `hint` to `AgentError` and include it in `to_dict()` only when set.
- [x] 2.2 Add `diagnostic_hint()` to the `AgentAdapter` protocol and implement it on `OpenCodeAdapter`, `CodeBuddyAdapter`, and `GenericCommandAdapter`.
- [x] 2.3 In `loop._parse_agent_error`, attach the adapter's diagnostic hint when the error is a generic provider-side server error; call the adapter defensively.
- [x] 2.4 Print the hint in `human._print_agent_failure` after the reference line.

## 3. Documentation and validation

- [x] 3.1 Add `docs/troubleshooting.md` covering the opencode `UnknownError`/`err_*` class of failure and the diagnostic command.
- [x] 3.2 Run focused tests, the full suite, lint/compile checks, and strict OpenSpec validation.
