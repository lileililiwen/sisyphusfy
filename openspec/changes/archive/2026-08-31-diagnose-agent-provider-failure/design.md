# Design: Diagnose agent provider failures

## Explore & Reuse

- Reuse `AgentError` (adapters.py) as the carrier. It already holds `name`,
  `message`, and `reference`; add an optional `hint` so the diagnostic guidance
  travels with the error and survives into JSON.
- Reuse the adapter protocol shape. `parse_error(output)` is already a per-adapter
  method; `diagnostic_hint()` follows the same pattern — each adapter returns the
  command that diagnoses *its* CLI, so sisyphusfy never hardcodes an agent-CLI
  detail and stays agent-agnostic.
- Reuse the error recovery path. `loop._parse_agent_error(adapter, result)` is
  the single place that turns agent output into an `AgentError`; it already calls
  the adapter defensively, so a missing `diagnostic_hint` cannot stop the loop.
- Reuse the human output path. `human._print_agent_failure(result)` already prints
  the error name/message and reference; add one hint line there when present.
- Detection stays generic. The loop decides whether to attach a hint from the
  *error content* (`name == "UnknownError"`, or a message mentioning server logs
  / a server-side error), never from agent-specific knowledge. The agent-specific
  command comes from `adapter.diagnostic_hint()`.

## Behavior

```python
# adapters.py
class AgentAdapter(Protocol):
    def parse_error(self, output: str) -> AgentError | None: ...
    def diagnostic_hint(self) -> str:
        """Return the command that diagnoses this agent CLI's failures."""

class OpenCodeAdapter:
    def diagnostic_hint(self) -> str:
        return "Run: opencode run 'hi' --print-logs --log-level DEBUG"

# loop.py, inside _parse_agent_error
error = adapter.parse_error(output) or AgentError()
if _is_provider_side(error):
    hint = _safe_diagnostic_hint(adapter)
    if hint:
        error.hint = hint
```

- `AgentError.to_dict()` includes `hint` only when set, so JSON stays additive.
- The human report prints the hint after the reference line, e.g.:
  `[agent] this is an agent-CLI/provider error, not a sisyphusfy failure.`
  `[agent] diagnose: opencode run 'hi' --print-logs --log-level DEBUG`

## Error handling and safety

- `_is_provider_side()` only triggers on generic server-error signals, so specific
  agent errors (e.g. a clear `RateLimitError`) are never masked by a hint.
- `_safe_diagnostic_hint()` calls the adapter defensively (a third-party adapter
  without the method degrades to no hint) so detection cannot stop the loop.
- No execution change: the hint is display-only and never fed back to a process.

## Verification

Add tests that an `UnknownError` envelope gets the opencode diagnostic hint in the
human report and in JSON; that a specific error gets no hint; that
`OpenCodeAdapter.diagnostic_hint()` returns the opencode command and the generic
adapter returns a generic one; and that `AgentError.to_dict()` round-trips the
hint. Run focused tests, the full suite, lint/compile checks, and strict OpenSpec
validation. Add `docs/troubleshooting.md` and a test that it documents the
`UnknownError` diagnosis.
