## 1. Testing

- [x] 1.1 Add a regression test proving a low-level external completion check runs in `--working-directory`.
- [x] 1.2 Add a test proving an explicitly configured completion-check directory is preserved.
- [x] 1.3 Add tests proving a missing agent, verification, or completion command returns `command_not_found` instead of raising.
- [x] 1.4 Add a test proving every release version literal agrees with `sisyphusfy.__version__`.
- [x] 1.5 Add a test proving the CI release workflow verifies the tag against the package version.

## 2. Completion check directory

- [x] 2.1 Scope the built-in external completion strategy to the loop working directory when it carries none.
- [x] 2.2 Preserve an explicitly configured completion-check directory.

## 3. Structured missing-command failures

- [x] 3.1 Classify a missing executable as `command_not_found` in `run_agent()`.
- [x] 3.2 Report `command_not_found` for missing agent and verification commands.
- [x] 3.3 Convert completion-check command failures into the same structured stop reason.

## 4. Release version metadata

- [x] 4.1 Make `sisyphusfy.__version__` the Python-side source of truth and drive the sdist/wheel version from it.
- [x] 4.2 Add a CI step that fails when the Git tag disagrees with the package version.

## 5. Release readiness and documentation

- [x] 5.1 Correct the roadmap so PyPI publication and version synchronization stay visible release-readiness gaps.
- [x] 5.2 Run the focused regression tests, then the full suite, Ruff, compileall, and `openspec validate --all --strict`.
- [x] 5.3 Update the handoff with the corrected claims, then archive the change.
