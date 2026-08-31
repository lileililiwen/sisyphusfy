# Proposal: Close the remaining post-commit audit gaps

## Why

An audit of `9648b58` confirmed the archived behaviors hold, but found four remaining gaps.

1. **Low-level external completion ignores `--working-directory`.** `cli.py` builds `ExternalCommandCompletion` without the selected directory, so the completion check runs in the caller's current directory while the agent and verification use the project directory. This contradicts the archived `supervisor-quality` contract and the README statement that every subprocess uses the selected project directory.
2. **Missing executables escape as raw exceptions.** `run_agent()` does not catch `FileNotFoundError`, and neither does low-level external completion. A missing agent, verification, or completion command can surface as a traceback instead of a structured, actionable result.
3. **Release version metadata is duplicated.** The Python package, npm launcher, npm manifest, and both installers each hardcode `0.1.0`. CI derives artifacts from the Git tag, so a future release can publish artifacts at one version while installers request another.
4. **PyPI publication is not automated or evidenced.** CI builds an sdist and wheel but never uploads them, so the roadmap claim that package distribution is complete is overstated.

Gaps 1–3 are product defects. Gap 4 is a release-readiness gap: this change corrects the roadmap and handoff claims instead of adding an unverifiable publish step, and documents what publication still requires.

## What changes

- Resolve the built-in external completion strategy's working directory from the loop's working directory, so `sisyphusfy loop -d <project> --completion-strategy external` checks in `<project>`.
- Classify a missing executable as `command_not_found` in `run_agent()` and report `command_not_found` as a loop stop reason with an actionable message for agent, verification, and completion-check commands.
- Make `sisyphusfy.__version__` the single Python-side source of truth, drive the sdist/wheel version from it, and enforce agreement with the npm launcher, npm manifest, and both installers by test.
- Add a CI step that fails a release when the Git tag does not match the package version.
- Correct the roadmap to keep an explicit release-readiness gap for PyPI publication and version synchronization.

## Non-goals

- No PyPI upload or trusted-publisher configuration; no npm publish. Publication still requires a registered project and confirmed credentials.
- No automatic version bumping or release tooling.
- No new agent, workflow, or release target.
- No change to the default opt-in nature of archive and commit hooks.

## Success criteria

External completion checks run in the selected directory, a missing command returns a structured `command_not_found` result instead of a traceback, one test keeps every version literal in agreement, CI rejects a tag that disagrees with the package version, and strict OpenSpec validation passes with the full suite green.
