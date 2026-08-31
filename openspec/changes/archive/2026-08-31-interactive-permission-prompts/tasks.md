## 1. Testing

- [x] 1.1 Add tests with a fake agent command that emits a blocked marker; in an interactive harness with a stubbed prompt returning "approve", assert the loop re-runs the agent in the same iteration and continues.
- [x] 1.2 Add a test: when the stubbed prompt returns "deny", the iteration stops with `blocked` and no further agent run occurs.
- [x] 1.3 Add a test: when the context is non-interactive (no terminal / `--json`), a blocked run stops with `blocked` and never prompts.
- [x] 1.4 Add a test: after the prompt cap is reached, the run stops with `blocked` (no infinite re-run).
- [x] 1.5 Add a test: verification and completion hooks do not run during a blocked re-run.

## 2. Interactive blocked resolution

- [x] 2.1 Add an `interactive` flag (config `interactive` + `--interactive`/`--no-interactive`), defaulting to terminal detection, and never interactive under `--json`.
- [x] 2.2 On a blocked marker in an interactive context, extract the blocker and present it to the user via an injectable prompt function.
- [x] 2.3 On an approve/free-text answer, re-run the agent in the same iteration with the answer folded into the prompt; on deny, stop with `blocked`.
- [x] 2.4 Bound the number of interactive re-prompts per iteration with a configurable cap (default 3).
- [x] 2.5 In non-interactive contexts, keep the existing stop-and-report `blocked` behavior unchanged.

## 3. Documentation and validation

- [x] 3.1 Document the interactive blocked-resolution behavior and its non-interactive fallback in the relevant docs (human-cli / troubleshooting).
- [x] 3.2 Run focused tests, the full suite, lint/compile checks, and strict OpenSpec validation.
