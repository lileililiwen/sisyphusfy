## Context

The `iteration-loop` spec promises that a blocked run in a terminal pauses for an explicit operator decision. The implementation split that promise across three sites — `LoopConfig` default, `human`/`cli` wiring, and the loop guard — and the default path was left unwired, so only tests (which inject `prompt_user`) ever prompt. Blocker extraction was written before configurable markers existed and still reads the global constant. No new concepts are needed; this change reconnects existing pieces.

## Goals / Non-Goals

**Goals:**
- `LoopConfig(interactive=True)` prompts out of the box with no caller setup.
- `sisyphusfy run / resume / loop --interactive` reaches the prompt path.
- Custom `blocked_markers` produce the same precise blocker text as default markers.

**Non-Goals:**
- No new prompt UI, key handling, or runtime commands.
- No change to `max_interactive_prompts` semantics or verification/hook gating.

## Explore & Reuse

- Reuse `_read_terminal_answer` as the default: it already denies on EOF/error so piped runs cannot hang; making it the field default (via `field(default_factory=...)` or `__post_init__`) keeps the injectable seam for tests.
- Reuse the existing guard `config.interactive and config.prompt_user is not None`; with the default set it becomes true exactly when intended, and `--json` still forces `interactive=False` upstream.
- Reuse `_marker_token_present` inside `_extract_blocker` by parameterizing the marker list, mirroring `_is_blocked(result, markers)`.
- Keep the loop engine agent-agnostic: blocker text stays a plain string, no adapter changes.

## Decisions

- **Default in `LoopConfig`, not at call sites.** One default fixes `human`, `cli`, and programmatic users at once; call-site wiring only needs to stop dropping the field. Alternative (set it in each caller) was rejected: three sites must stay in sync.
- **Keep deny-on-empty, but echo it.** Changing empty to approve would risk auto-continuing past privileged blockers on an accidental Enter; printing `denied (empty input)` removes the silent-abort surprise without weakening safety.
- **No signature break:** `_extract_blocker(result, markers=None)` keeps existing callers and tests compiling; `None` means the global defaults.

## Risks / Trade-offs

- [Risk] Default prompt activates in any `interactive=True` embedding that previously relied on the silent no-op → Mitigation: that combination was documented as prompting, so this restores the contract; `--no-interactive` remains the opt-out.
- [Risk] Custom-marker blocker text changes what operators see → Mitigation: it changes from a full-output dump to the precise marker lines, strictly more readable; covered by a new test.
