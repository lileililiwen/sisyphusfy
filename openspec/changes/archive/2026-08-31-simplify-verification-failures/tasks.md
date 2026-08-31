## 1. Testing

- [x] 1.1 Add detector tests for deterministic precedence across .NET, Rust, Python, JavaScript, Flutter, and Makefile projects.
- [x] 1.2 Add regression tests proving .NET repositories do not resolve to `make test` and Makefile detection requires a declared `test` target.
- [x] 1.3 Add tests proving explicit verification commands override discovery and no-detector projects are reported clearly.
- [x] 1.4 Add loop and CLI tests for retained verification evidence, concise default output, explicit diagnostic output, and JSON fields.
- [x] 1.5 Add log-retention and output-bounding tests, including timeout and non-zero verification cases.

## 2. Verification discovery

- [x] 2.1 Implement marker-aware, deterministic verification discovery behind the existing configuration entry point.
- [x] 2.2 Add .NET solution/project detection and safe Makefile `test` target detection.
- [x] 2.3 Add supported Rust, Python, JavaScript, and Flutter/Dart detectors with explicit executable checks.
- [x] 2.4 Expose configured, discovered, and unavailable verification sources through dry-run and doctor output.

## 3. Verification diagnostics

- [x] 3.1 Retain the verification `RunResult` in `LoopResult` without changing verification ordering or stop semantics.
- [x] 3.2 Persist bounded per-run/per-iteration verification logs without writing secrets or invoking shell commands.
- [x] 3.3 Add concise human failure output with verifier status and log path.
- [x] 3.4 Add an explicit verbose/log-inspection path and structured JSON metadata.

## 4. Documentation and validation

- [x] 4.1 Document discovery precedence, explicit configuration, diagnostic locations, retention, and verbose inspection.
- [x] 4.2 Clarify that verification success is not equivalent to a full product smoke test.
- [x] 4.3 Run focused tests, the full suite, lint/compile checks, and strict OpenSpec validation.
