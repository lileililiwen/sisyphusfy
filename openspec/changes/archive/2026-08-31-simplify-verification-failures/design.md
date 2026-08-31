# Design: Simplify verification failures

## Explore & Reuse

- Reuse `find_verification_command()` as the public discovery entry point, but
  move selection into ordered marker-aware detector functions so the policy is
  testable and replaceable.
- Reuse `run_agent()` and `RunResult` for subprocess execution, timeout, exit
  status, and byte decoding. Verification evidence must be represented by the
  same structured result rather than a second subprocess implementation.
- Reuse `LoopResult.to_dict()` and the existing human result formatter; add a
  verification evidence field instead of printing subprocess output from the
  loop engine.
- Preserve the generic core boundary: ecosystem detectors are small built-in
  discovery adapters, and explicit `verification_command` remains the generic
  configuration escape hatch.

## Behavior

When the configured verification command is non-empty, Sisyphusfy executes it
unchanged and labels its source as `configured`. When it is empty, discovery
examines repository files and supported executable availability. Detection uses
deterministic precedence and validates repository-specific inputs before
returning a command:

1. .NET solution or project marker -> `dotnet test` with the discovered
   solution/project path when available;
2. Rust manifest -> `cargo test`;
3. Python project/test configuration -> `pytest`;
4. JavaScript package manifest with a test script -> `npm test`;
5. Flutter/Dart project marker -> `flutter test`;
6. Makefile with a declared `test` target -> `make test`.

The implementation must document the exact marker and executable checks and
must not infer a Make target from the presence of `make` alone. If no detector
matches, `doctor` reports that no verifier was found and the loop does not
pretend that verification passed.

Each verification invocation returns a structured `RunResult` retained in the
`LoopResult`, including command, working directory, exit status, classification,
timeout state, and bounded stdout/stderr. The complete untruncated streams are
written to a generated local log file under the configured project state/log
location, with a stable path reported in the result. Log filenames identify the
run and iteration, and retention is bounded so repeated loops cannot grow
without limit. Logs are local diagnostics, are not committed or archived by
Sisyphusfy, and the implementation must avoid printing environment values.

Default human output reports only the verifier, exit status or timeout, and log
path. A deliberate verbose/log-inspection option prints or opens the saved
diagnostics. JSON reports the verification command, source, status, and log
path; full stdout/stderr require an explicit diagnostic option so automation
does not accidentally expose large or sensitive output.

## Error handling and safety

Detection is read-only except for creating the diagnostic log after a command
has run. It must never execute a candidate verifier merely to discover whether
it exists, and it must never invoke a shell. Missing executables, malformed
project metadata, verifier timeouts, and non-zero exits remain structured
outcomes. A detector failure must not silently fall through to an unrelated
ecosystem command. Explicit commands continue to be user-controlled executable
input and retain existing timeout and working-directory safeguards.

## Verification

Add unit tests for detector precedence, .NET solution selection, Makefile test
target validation, explicit-command precedence, no-detector behavior, and
missing executables. Add loop and CLI tests proving failed verification retains
structured evidence, writes a bounded log, keeps default output concise, and
exposes full diagnostics only through the explicit option. Run the focused
tests, full test suite, lint/compile checks, and strict OpenSpec validation.
