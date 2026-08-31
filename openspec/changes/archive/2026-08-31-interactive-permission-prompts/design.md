# Design: Interactive permission prompts

## Explore & Reuse

- Reuse the existing blocked path. `loop` already detects a configured blocked
  marker in agent output and stops with a `blocked` result before verification and
  hooks (`iteration-loop` spec). The interactive path is a branch taken *instead of*
  stopping when a terminal is available.
- Reuse `run_agent()` and the adapter `build_command(working_directory, prompt)`.
  The answer is folded into a new prompt and the agent is re-invoked with the same
  adapter/working directory, preserving workspace state on disk (task/handoff
  files). This is the disposable model sisyphusfy already uses; we are not keeping
  a process alive.
- Reuse the human prompt surface. The `human`/`cli` layer already distinguishes
  interactive from non-interactive (it disables the progress sink under `--json` and
  writes to stderr). The permission prompt is a small, explicit input read from the
  terminal; in tests it is supplied as an injectable function so fake agent
  commands cover the full flow.
- Keep the loop engine agent-agnostic. The blocker text and the answer are just
  strings passed through `build_command`; no adapter-specific logic is added.
- Reuse the safety rules. A privileged/destructive blocker is shown verbatim and
  requires an explicit allow/deny; denial stops the iteration with `blocked` exactly
  as today.

## Behavior

```python
# pseudo-flow inside the iteration loop
result = run_agent(adapter, working_dir, prompt, ...)
if result.exit_status != 0 and _has_blocked_marker(result):
    blocker = _extract_blocker(result)
    if not interactive:
        return _blocked_stop(blocker)            # unchanged behavior
    for _ in range(max_interactive_prompts):
        answer = prompt_user(blocker)            # explicit input, never silent
        if answer.denied:
            return _blocked_stop(blocker)
        result = run_agent(
            adapter, working_dir,
            _augment_prompt(prompt, blocker, answer),
        )
        if not _has_blocked_marker(result):
            break                                 # continued; loop proceeds
    else:
        return _blocked_stop(blocker)            # gave up after N prompts
```

- `interactive` is true when a terminal is attached and `--json`/`--no-interactive`
  are not set, or when `--interactive` is passed explicitly. CI/piped runs are
  non-interactive by default.
- `_augment_prompt` appends the blocker and the user's decision to the original
  prompt so the fresh agent invocation has the context to continue. The exact
  wording is adapter-agnostic prompt text.
- `max_interactive_prompts` (default small, e.g. 3) bounds re-runs so an
  unresolvable blocker cannot loop forever; after it is exhausted the run stops
  with `blocked` as today.

## Error handling and safety

- Non-interactive contexts must not block: the prompt is only offered when input is
  genuinely available, so `--json` and CI never hang.
- Denial or an unresolvable blocker ends the iteration with `blocked`; verification
  and hooks still do not run, matching the existing contract.
- A privileged/destructive blocker is never auto-approved; the prompt requires an
  explicit response and the user may deny.
- The re-run is a normal `run_agent` call with timeout/exit handling unchanged, so
  timeouts and interrupts behave as before.

## Verification

Add tests with fake agent commands that (1) emit a blocked marker and, in an
  interactive harness with a stubbed prompt, continue after an "approve" answer;
  (2) stop with `blocked` when the prompt is denied; (3) fall back to stop+report
  when the context is non-interactive; (4) stop after the prompt cap is reached.
  Confirm verification and hooks still do not run on a blocked re-run. Run focused
  tests, the full suite, lint/compile checks, and strict OpenSpec validation.
