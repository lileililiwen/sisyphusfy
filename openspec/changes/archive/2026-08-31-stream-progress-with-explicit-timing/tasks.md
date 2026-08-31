## 1. Testing

- [x] 1.1 Add duration-format tests for `0s`, short seconds, and `Nm Ns` values.
- [x] 1.2 Add streaming and heartbeat tests for agent and verification subprocesses.
- [x] 1.3 Add timeout tests proving partial output and the diagnostic path are shown immediately.
- [x] 1.4 Add Ctrl-C tests proving durable state preservation and archive/commit hook suppression.
- [x] 1.5 Add tests proving progress output never corrupts JSON and output remains bounded.

## 2. Live progress

- [x] 2.1 Add a streaming subprocess output path with component labels and idle heartbeats.
- [x] 2.2 Add one explicit elapsed-duration formatter and use it for all human-facing timing.
- [x] 2.3 Report partial timeout diagnostics and log paths immediately.
- [x] 2.4 Add safe interruption classification and suppress completion hooks after interruption.

## 3. Documentation and validation

- [x] 3.1 Document progress labels, heartbeat behavior, timing format, interruption behavior, and JSON rules.
- [x] 3.2 Run focused tests, the full suite, lint/compile checks, and strict OpenSpec validation.
