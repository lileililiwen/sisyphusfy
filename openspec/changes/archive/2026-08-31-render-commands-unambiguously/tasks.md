## 1. Testing

- [x] 1.1 Add formatter tests: multi-word arguments quoted, simple commands unchanged, empty command safe.
- [x] 1.2 Add a diagnostic-log test proving the `command:` header shows argument boundaries.
- [x] 1.3 Add human-output tests for the agent-failure, timeout, and verification-status command lines.
- [x] 1.4 Add a test proving JSON still reports `command` as a list, unquoted.

## 2. Display commands unambiguously

- [x] 2.1 Add one shared command formatter next to `RunResult`.
- [x] 2.2 Use it in the diagnostic log header.
- [x] 2.3 Use it in the human agent-failure, timeout, and verification-status reports.
- [x] 2.4 Use it in `doctor`, dry-run, and the low-level single-command output.

## 3. Documentation and validation

- [x] 3.1 Note the display rule where command execution is documented.
- [x] 3.2 Run focused tests, the full suite, lint/compile checks, and strict OpenSpec validation.
