## 1. Testing

- [x] 1.1 Add a test: `LoopConfig(interactive=True)` without an explicit `prompt_user` still prompts (stub stdin) and continues on approval.
- [x] 1.2 Add a test: `_extract_blocker` with custom `blocked_markers` returns the custom marker lines, not the full-output fallback.
- [x] 1.3 Add a test: empty input denies and the denial path stops with `blocked` without re-running the agent.

## 2. Prompt wiring

- [x] 2.1 Default `LoopConfig.prompt_user` to `_read_terminal_answer` while keeping it injectable.
- [x] 2.2 Pass `interactive` + `prompt_user` through `human._execute_loop` and `cli._run_loop` into `LoopConfig`.
- [x] 2.3 Parameterize `_extract_blocker(result, markers=None)` on configured markers and update loop call sites.

## 3. Documentation and validation

- [x] 3.1 Correct the interactive behavior docs where they assume wiring that was missing.
- [x] 3.2 Run focused tests, the full suite, `ruff check`, `compileall`, and `openspec validate --all --strict`.
