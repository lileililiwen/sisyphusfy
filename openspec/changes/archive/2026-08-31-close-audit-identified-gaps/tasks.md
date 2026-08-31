## 1. Testing

- [x] 1.1 Add a regression test proving low-level dry-run does not execute an external completion check.
- [x] 1.2 Add regression tests proving verification runs once per iteration and runs before hooks when state is initially complete.
- [x] 1.3 Add regression tests proving high-level `--project-dir` is used by agent, verification, workflow, archive, and commit subprocesses.
- [x] 1.4 Add tests that supported release metadata and CI matrix entries cannot advertise a mislabeled binary.
- [x] 1.5 Add documentation contract tests for the public configuration schema, adapter protocol, examples, and security guidance.

## 2. Loop and CLI correctness

- [x] 2.1 Centralize completion/verification ordering and remove duplicate verification execution.
- [x] 2.2 Propagate and normalize the project working directory across all subprocess boundaries.
- [x] 2.3 Make low-level dry-run side-effect free for completion and workflow adapters while preserving planned output.
- [x] 2.4 Preserve structured failure results and explicit opt-in archive/commit behavior.

## 3. Public contracts and release truth

- [x] 3.1 Document every supported `.sisyphusfy.toml` field, type, default, precedence, and safety behavior.
- [x] 3.2 Document the `AgentAdapter` protocol, registry extension path, command construction, model support, and failure classification.
- [x] 3.3 Add minimal end-to-end examples for Python, Rust, JavaScript, Flutter, and .NET projects.
- [x] 3.4 Add CI usage examples and a command-execution security review covering configured agent, verification, workflow, archive, and commit commands.
- [x] 3.5 Make release platform/architecture metadata and CI build targets consistent; defer unsupported targets rather than mislabeling them.

## 4. Verification and documentation

- [x] 4.1 Run the focused regression and documentation tests.
- [x] 4.2 Run the full test suite, Ruff, compileall, and `openspec validate --all --strict`.
- [x] 4.3 Update roadmap and handoff claims only after the implementation evidence is complete.
