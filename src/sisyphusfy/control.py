"""Interactive loop controls: ESC pause and blocked-prompt slash commands.

This module owns the operator control surface of a running loop. It is
agent-agnostic: it steers the loop (pause, model selection, handoff
compaction), never the agent CLI's internals.

v1 scope: ESC is honored at safe points only (iteration boundaries and
inside the blocked prompt). A running subprocess is never suspended;
an ESC arriving mid-invocation sets a pending pause honored when that
invocation returns. No PTY multiplexing, no mid-subprocess SIGSTOP.
"""

from __future__ import annotations

import os
import select
import sys
import threading
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

try:  # POSIX-only; Windows keeps Ctrl-C behavior (documented limitation).
    import termios
    import tty
except ImportError:  # pragma: no cover - non-POSIX platform
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

ESC = "\x1b"

SLASH_HELP = (
    "Control commands (never sent to the agent):\n"
    "  /models [name]  list the chain with active/skip marks, or switch to <name>\n"
    "  /compact        compact the handoff file now and report counts\n"
    "  /help           show this help\n"
    "  /resume         continue the run\n"
    "  /stop           stop the run\n"
    "  step            (pause menu) run one iteration, then pause again"
)


@dataclass
class ControlState:
    """Mutable operator-control state for one loop run."""

    pending_pause: bool = False
    pause_count: int = 0
    model_switches: list[str] = field(default_factory=list)
    active_model: str | None = None
    step_after: bool = False


@dataclass
class SlashResult:
    """Outcome of one REPL input line.

    ``action`` is one of ``reprompt`` (handled, ask again), ``answer``
    (plain text for the agent prompt), ``resume``, ``stop``, or
    ``step``. Only ``answer`` text may reach the agent.
    """

    action: str
    text: str = ""


def classify_key(data: bytes) -> str:
    """Classify raw terminal bytes: ``esc``, ``csi``, ``meta``, ``other``.

    A lone ESC byte is the pause key. CSI sequences (arrows, ``ESC [`` /
    ``ESC O`` prefixed) and ESC-plus-character (Alt-key) sequences MUST
    NOT pause.
    """
    if not data:
        return "empty"
    if data == b"\x1b":
        return "esc"
    if data.startswith((b"\x1b[", b"\x1bO")):
        return "csi"
    if data.startswith(b"\x1b"):
        return "meta"
    return "other"


def feed_key(state: ControlState, data: bytes) -> bool:
    """Feed raw bytes; return True when a pause was requested."""
    if classify_key(data) == "esc":
        state.pending_pause = True
        return True
    return False


class KeyWatcher:
    """Background ESC listener, active only on an interactive POSIX tty.

    The thread ticks on ``select`` and never blocks the loop; while the
    loop holds the terminal for a line prompt it MUST suspend the
    watcher (see :meth:`suspended`) so keystrokes are not stolen from
    the prompt. ``start`` is a no-op returning False when stdin is not
    a TTY or the platform lacks ``termios``.
    """

    def __init__(self, state: ControlState) -> None:
        self._state = state
        self._stop = threading.Event()
        self._suspended = threading.Event()
        self._thread: threading.Thread | None = None
        self.active = False

    def start(self) -> bool:
        if termios is None or tty is None:
            return False
        try:
            is_tty = sys.stdin.isatty()
        except (OSError, ValueError):
            return False
        if not is_tty or os.name != "posix":
            return False
        self._thread = threading.Thread(
            target=self._run, name="sisyphusfy-keys", daemon=True
        )
        self._thread.start()
        self.active = True
        return True

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        self.active = False
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    @contextmanager
    def suspended(self):  # type: ignore[no-untyped-def]
        """Suspend byte reading while the loop holds the terminal."""
        self._suspended.set()
        try:
            yield
        finally:
            self._suspended.clear()

    def _run(self) -> None:
        try:
            fd = sys.stdin.fileno()
        except (OSError, ValueError):
            return
        try:
            saved = termios.tcgetattr(fd)
        except termios.error:
            return
        try:
            tty.setcbreak(fd)
            while not self._stop.is_set():
                if self._suspended.is_set():
                    self._stop.wait(0.05)
                    continue
                try:
                    ready, _, _ = select.select([fd], [], [], 0.1)
                except (OSError, ValueError):
                    return
                if not ready:
                    continue
                try:
                    first = os.read(fd, 1)
                except OSError:
                    return
                if first != b"\x1b":
                    continue
                try:
                    more_ready, _, _ = select.select([fd], [], [], 0.05)
                except (OSError, ValueError):
                    return
                if more_ready:
                    try:
                        rest = os.read(fd, 16)
                    except OSError:
                        return
                    feed_key(self._state, first + rest)
                else:
                    feed_key(self._state, first)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, saved)
            except (termios.error, OSError):
                pass


def parse_slash(text: str) -> tuple[str, str] | None:
    """Split ``/cmd [arg]`` input; return None for non-slash input."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split(None, 1)
    return (parts[0].lower(), parts[1].strip() if len(parts) > 1 else "")


@dataclass
class ReplContext:
    """Static resources the slash dispatcher may use (no loop imports)."""

    model_chain: list[str] = field(default_factory=list)
    default_model: str | None = None
    supports_model: Callable[[str], bool] = lambda _m: True
    handoff_path: str | None = None
    on_compact: Callable[[], object | None] = lambda: None
    emit: Callable[[str], None] | None = None

    def say(self, message: str) -> None:
        if self.emit is not None:
            self.emit(message)
        else:
            sys.stderr.write(message + "\n")
            sys.stderr.flush()


def _render_models(ctx: ReplContext, state: ControlState) -> str:
    active = state.active_model or ctx.default_model
    lines = ["Available models:"]
    if not ctx.model_chain:
        marker = " (default)" if ctx.default_model else ""
        lines.append(f"  * {active or '(none configured)'}{marker}")
        return "\n".join(lines)
    for name in ctx.model_chain:
        marks = []
        if name == active:
            marks.append("active")
        try:
            supported = ctx.supports_model(name)
        except Exception:  # noqa: BLE001 - a custom adapter must not break the REPL
            supported = True
        if not supported:
            marks.append("unsupported")
        suffix = f" [{', '.join(marks)}]" if marks else ""
        lines.append(f"  {'*' if name == active else '-'} {name}{suffix}")
    return "\n".join(lines)


def dispatch_slash(
    cmd: str, arg: str, ctx: ReplContext, state: ControlState
) -> SlashResult:
    """Execute one slash command; slash input never becomes agent text."""
    if cmd == "/models":
        if not arg:
            ctx.say(_render_models(ctx, state))
            return SlashResult("reprompt")
        try:
            supported = ctx.supports_model(arg)
        except Exception:  # noqa: BLE001 - a custom adapter must not break the REPL
            supported = True
        if not supported:
            ctx.say(f"Model {arg!r} is not supported by the adapter; keeping current model.")
            return SlashResult("reprompt")
        state.active_model = arg
        state.model_switches.append(arg)
        ctx.say(f"Switched to model {arg!r} for subsequent invocations.")
        return SlashResult("reprompt")
    if cmd == "/compact":
        result = ctx.on_compact()
        if result is None:
            ctx.say("No handoff file configured; nothing compacted.")
        else:
            before = getattr(result, "before_chars", "?")
            after = getattr(result, "after_chars", "?")
            ctx.say(f"Compacted handoff: {before} -> {after} chars.")
        return SlashResult("reprompt")
    if cmd == "/help":
        ctx.say(SLASH_HELP)
        return SlashResult("reprompt")
    if cmd == "/resume":
        return SlashResult("resume")
    if cmd == "/stop":
        return SlashResult("stop")
    ctx.say(f"Unknown command {cmd!r}.\n{SLASH_HELP}")
    return SlashResult("reprompt")


def handle_prompt_text(
    text: str, ctx: ReplContext, state: ControlState
) -> SlashResult:
    """Route one REPL input line to slash handling or a plain answer."""
    if ESC in text:
        # An ESC typed at the prompt requests a pause; it must never
        # leak control bytes into the agent prompt.
        state.pending_pause = True
        return SlashResult("reprompt")
    parsed = parse_slash(text)
    if parsed is None:
        return SlashResult("answer", text)
    cmd, arg = parsed
    return dispatch_slash(cmd, arg, ctx, state)


def pause_menu(
    read_answer: Callable[[str], object],
    ctx: ReplContext,
    state: ControlState,
) -> str:
    """Offer resume / stop / step-once; same slash parser as the prompt.

    ``read_answer`` takes a blocker label and returns a
    :class:`PromptAnswer`-shaped object (``denied``/``text``), so tests
    can drive the menu through the existing ``prompt_user`` seam.
    Returns ``"resume"``, ``"stop"``, or ``"step"``.
    """
    ctx.say("Paused. Type resume, stop, step, or a /command (/help for list).")
    while True:
        answer = read_answer("paused")
        text = (getattr(answer, "text", "") or "").strip()
        denied = bool(getattr(answer, "denied", False))
        if denied and not text:
            return "resume"
        decision = handle_prompt_text(text, ctx, state)
        if decision.action == "reprompt":
            continue
        if decision.action == "stop":
            return "stop"
        if decision.action == "resume":
            return "resume"
        lowered = decision.text.strip().lower() if decision.action == "answer" else ""
        if lowered in {"resume", "continue", "approve", "yes", "y", ""}:
            return "resume"
        if lowered in {"stop", "quit", "deny", "no", "n", "q"}:
            return "stop"
        if lowered in {"step", "step-once", "step once"}:
            return "step"
        ctx.say(f"Unknown choice {decision.text.strip()!r}. Type resume, stop, or step.")
