"""Process-group cleanup tests for runner timeout/interrupt handling.

The runner MUST launch bounded subprocesses so that a timeout or interrupt
attempts to terminate the launched process and its descendants, not only the
direct child. Reader threads must still drain with the existing grace period,
and the structured timeout/interrupted classification must be preserved.
"""

from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

from sisyphusfy.result import Classification
from sisyphusfy.runner import run_agent

_POSIX = pytest.mark.skipif(
    sys.platform == "win32",
    reason="process-group kill relies on POSIX killpg/setsid",
)


def _script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


def _pid_alive(pid: int) -> bool:
    """Return True if `pid` is still a running process on POSIX."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@_POSIX
class TestProcessGroupTimeout:
    def test_descendant_is_stopped_on_timeout(self, tmp_path: Path) -> None:
        """A child forked by the agent must be reaped by the runner timeout."""
        child_pid_path = tmp_path / "child.pid"
        marker = tmp_path / "child.marker"

        agent = _script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            import os
            import sys
            import time
            pid = os.fork()
            if pid == 0:
                try:
                    Path({str(marker)!r}).write_text("alive")
                    Path({str(child_pid_path)!r}).write_text(str(os.getpid()))
                except Exception:
                    os._exit(1)
                time.sleep(30)
                os._exit(0)
            # Parent waits for the grandchild so the agent itself is slow.
            _, status = os.waitpid(pid, 0)
            sys.exit(status >> 8)
            """,
        )

        start = time.monotonic()
        result = run_agent(agent, working_directory=tmp_path, timeout=0.5)
        elapsed = time.monotonic() - start

        assert result.timed_out is True
        assert result.classification == Classification.TIMEOUT
        # If group cleanup works, the runner returns well before the 30s sleep.
        assert elapsed < 10.0, f"runner waited too long: {elapsed:.2f}s"

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not child_pid_path.exists():
            time.sleep(0.05)
        assert child_pid_path.exists(), "child never wrote its pid"
        child_pid = int(child_pid_path.read_text().strip())
        # The grandchild must be gone after the runner timed out.
        assert not _pid_alive(child_pid), "descendant survived runner timeout"

    def test_direct_child_classifies_timeout_unchanged(
        self, tmp_path: Path
    ) -> None:
        """Timeout classification is preserved while group cleanup runs."""
        agent = _script(
            tmp_path,
            "slow.py",
            "import time; time.sleep(30)",
        )
        result = run_agent(agent, working_directory=tmp_path, timeout=0.2)
        assert result.timed_out is True
        assert result.classification == Classification.TIMEOUT
        assert result.interrupted is False
