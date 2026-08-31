"""The single bounded subprocess boundary for agents and verification.

Output is streamed line by line to optional progress callbacks while the child
runs, and is still captured in full so results keep their evidence. Timeouts and
interruptions stop the child through the same cleanup path and keep whatever
output was already received.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from sisyphusfy.progress import DEFAULT_HEARTBEAT_SECONDS
from sisyphusfy.result import Classification, RunResult

# Conventional shell exit status for a command that could not be executed.
COMMAND_NOT_FOUND_EXIT_STATUS = 127

# How often the runner checks for exit, timeout, and heartbeat conditions.
POLL_SECONDS = 0.05

# How long to wait for a stopped child to be reaped.
STOP_GRACE_SECONDS = 5.0

# How long reader threads may take to drain after the child stops.
DRAIN_GRACE_SECONDS = 5.0


class _Activity:
    """How long a subprocess has produced no output."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last = time.monotonic()

    def touch(self) -> None:
        with self._lock:
            self._last = time.monotonic()

    def idle(self) -> float:
        with self._lock:
            return time.monotonic() - self._last


class _Progress:
    """Forward progress events without letting a closed stream kill the child.

    A broken pipe or a closed output stream disables progress; the child keeps
    running and its result is still classified normally.
    """

    def __init__(
        self,
        on_output: Callable[[str], None] | None = None,
        on_heartbeat: Callable[[float, float], None] | None = None,
    ) -> None:
        self._on_output = on_output
        self._on_heartbeat = on_heartbeat
        self._enabled = True

    def line(self, text: str) -> None:
        if not self._enabled or self._on_output is None:
            return
        try:
            self._on_output(text)
        except (BrokenPipeError, OSError, ValueError):
            self._enabled = False

    def heartbeat(self, elapsed_seconds: float, idle_seconds: float) -> None:
        if not self._enabled or self._on_heartbeat is None:
            return
        try:
            self._on_heartbeat(elapsed_seconds, idle_seconds)
        except (BrokenPipeError, OSError, ValueError):
            self._enabled = False


def _read_lines(stream, chunks: list[str], activity: _Activity, progress: _Progress) -> None:
    """Capture one stream and forward each complete line as progress."""
    try:
        for raw in iter(stream.readline, b""):
            text = raw.decode(errors="replace")
            chunks.append(text)
            activity.touch()
            line = text.rstrip("\r\n").strip()
            if line:
                progress.line(line)
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _write_stdin(stream, data: bytes) -> None:
    """Send the prompt without blocking on a child that never reads it."""
    try:
        stream.write(data)
        stream.flush()
    except (BrokenPipeError, OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _stop(proc: subprocess.Popen) -> None:
    """Terminate a child and reap it."""
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass


def _pump(
    proc: subprocess.Popen,
    timeout: float,
    start: float,
    progress: _Progress,
    heartbeat_interval: float,
) -> tuple[str, str, bool, bool]:
    """Wait for the child while emitting heartbeats and enforcing the timeout.

    Returns the captured stdout, stderr, whether the child timed out, and
    whether it was interrupted.
    """
    activity = _Activity()
    chunks_out: list[str] = []
    chunks_err: list[str] = []
    readers = [
        threading.Thread(
            target=_read_lines, args=(stream, chunks, activity, progress), daemon=True
        )
        for stream, chunks in ((proc.stdout, chunks_out), (proc.stderr, chunks_err))
    ]
    for reader in readers:
        reader.start()

    deadline = start + timeout
    last_beat = start
    timed_out = False
    interrupted = False

    try:
        while proc.poll() is None:
            now = time.monotonic()
            if now >= deadline:
                timed_out = True
                break
            if (
                now - last_beat >= heartbeat_interval
                and activity.idle() >= heartbeat_interval
            ):
                progress.heartbeat(now - start, activity.idle())
                last_beat = now
            time.sleep(min(POLL_SECONDS, deadline - now))
    except KeyboardInterrupt:
        interrupted = True

    if timed_out or interrupted:
        _stop(proc)
    for reader in readers:
        reader.join(DRAIN_GRACE_SECONDS)

    return "".join(chunks_out), "".join(chunks_err), timed_out, interrupted


def run_agent(
    command: list[str],
    *,
    working_directory: str | Path = ".",
    prompt: str | None = None,
    timeout: float = 60.0,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    on_output: Callable[[str], None] | None = None,
    on_heartbeat: Callable[[float, float], None] | None = None,
    heartbeat_interval: float = DEFAULT_HEARTBEAT_SECONDS,
) -> RunResult:
    """Run one command as an argument list, streaming progress as it runs."""
    cwd = str(Path(working_directory).resolve())

    if dry_run:
        return RunResult(
            command=command,
            exit_status=None,
            classification=Classification.DRY_RUN,
            working_directory=cwd,
            prompt=prompt,
            env=env or {},
        )

    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    stdin_data = (prompt + "\n").encode() if prompt else None

    start = time.monotonic()
    progress = _Progress(on_output, on_heartbeat)

    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
        )
    except FileNotFoundError as exc:
        return RunResult(
            command=command,
            exit_status=COMMAND_NOT_FOUND_EXIT_STATUS,
            classification=Classification.COMMAND_NOT_FOUND,
            stderr=f"command not found: {command[0] if command else ''}",
            working_directory=cwd,
            prompt=prompt,
            env=env or {},
            error=str(exc),
        )

    if stdin_data:
        writer = threading.Thread(
            target=_write_stdin, args=(proc.stdin, stdin_data), daemon=True
        )
        writer.start()
    else:
        _write_stdin(proc.stdin, b"")

    stdout, stderr, timed_out, interrupted = _pump(
        proc, timeout, start, progress, heartbeat_interval
    )
    duration = (time.monotonic() - start) * 1000
    exit_status = proc.returncode if proc.returncode is not None else -1

    if interrupted:
        classification = Classification.INTERRUPTED
    elif timed_out:
        classification = Classification.TIMEOUT
    elif exit_status == 0:
        classification = Classification.SUCCESS
    else:
        classification = Classification.FAILURE

    return RunResult(
        command=command,
        exit_status=exit_status,
        classification=classification,
        stdout=stdout,
        stderr=stderr,
        duration_ms=round(duration, 2),
        timed_out=timed_out,
        interrupted=interrupted,
        working_directory=cwd,
        prompt=prompt,
        env=env or {},
    )
