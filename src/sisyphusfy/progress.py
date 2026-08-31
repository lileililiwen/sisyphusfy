"""Live progress for human-facing subprocess output.

The loop engine returns structured evidence for automation; this module only
carries the human-facing stream of progress lines and idle heartbeats. Callers
that ask for machine-readable output never receive progress.

Every elapsed value is rendered by one formatter so a duration can never be
misread as a bare number or an ambiguous clock value.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Protocol, TextIO, runtime_checkable

# Progress lines are tagged with the component that produced them.
COMPONENT_AGENT = "agent"
COMPONENT_VERIFY = "verify"

# How long a subprocess may stay silent before a heartbeat is emitted.
DEFAULT_HEARTBEAT_SECONDS = 15.0


def format_duration(seconds: float) -> str:
    """Render an elapsed duration with explicit units.

    Durations below one minute render as `42s`; longer durations render as
    `1m 12s`. Zero renders as `0s`.
    """
    total = max(0, int(seconds))
    minutes, remainder = divmod(total, 60)
    if minutes:
        return f"{minutes}m {remainder}s"
    return f"{remainder}s"


@runtime_checkable
class ProgressSink(Protocol):
    """Receives live progress for one loop run."""

    def line(self, component: str, text: str) -> None:
        """Handle one output line from `component`."""

    def heartbeat(
        self,
        component: str,
        elapsed_seconds: float,
        idle_seconds: float,
    ) -> None:
        """Report that `component` produced no output for `idle_seconds`."""


class StreamProgress:
    """Print labelled progress lines to a human-readable stream.

    Progress goes to stderr by default so it never mixes with the concise
    human result or with machine-readable JSON on stdout.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stderr

    def line(self, component: str, text: str) -> None:
        self._write(f"[{component}] {text}")

    def heartbeat(
        self,
        component: str,
        elapsed_seconds: float,
        idle_seconds: float,
    ) -> None:
        self._write(
            f"[{component}] no output for {format_duration(idle_seconds)} "
            f"(elapsed {format_duration(elapsed_seconds)})"
        )

    def _write(self, text: str) -> None:
        print(text, file=self._stream, flush=True)


def progress_callbacks(
    sink: ProgressSink | None,
    component: str,
) -> tuple[Callable[[str], None] | None, Callable[[float, float], None] | None]:
    """Bind a progress sink to one component for the subprocess runner."""
    if sink is None:
        return None, None
    return (
        lambda text: sink.line(component, text),
        lambda elapsed, idle: sink.heartbeat(component, elapsed, idle),
    )
