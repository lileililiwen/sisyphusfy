"""Tests for the shared bounded subprocess execution primitive.

The primitive is the single source of truth for subprocess execution: it bounds
in-memory output, writes a complete local diagnostic log when asked, runs
descendants in their own process group, and classifies the result so callers
can map it to their own result type (loop, hook, workflow).
"""

from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

from sisyphusfy.diagnostics import (
    bound_output,
    subprocess_log_dir,
    subprocess_log_path,
    write_subprocess_log,
)
from sisyphusfy.result import Classification
from sisyphusfy.runner import run_command

_POSIX = pytest.mark.skipif(
    sys.platform == "win32",
    reason="process-group kill relies on POSIX killpg/setsid",
)


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return False


class TestBoundedCapture:
    def test_output_capped_at_max_output_bytes(self, tmp_path: Path) -> None:
        body = "import sys; sys.stdout.write('x' * 5000); sys.stdout.flush()"
        cmd = _write_script(tmp_path, "noisy.py", body)
        result = run_command(cmd, working_directory=tmp_path, max_output_bytes=256)
        assert result.exit_status == 0
        assert len(result.stdout) <= 256
        assert result.truncated is True

    def test_output_under_bound_is_not_truncated(self, tmp_path: Path) -> None:
        body = "print('hello')"
        cmd = _write_script(tmp_path, "quiet.py", body)
        result = run_command(cmd, working_directory=tmp_path, max_output_bytes=4096)
        assert result.exit_status == 0
        assert result.stdout.strip() == "hello"
        assert result.truncated is False

    def test_stderr_is_also_bounded(self, tmp_path: Path) -> None:
        body = (
            "import sys\n"
            "sys.stderr.write('y' * 4000)\n"
            "sys.stderr.flush()\n"
        )
        cmd = _write_script(tmp_path, "noisy_err.py", body)
        result = run_command(cmd, working_directory=tmp_path, max_output_bytes=128)
        assert len(result.stderr) <= 128
        assert result.truncated is True

    def test_default_max_output_bytes_is_known(self, tmp_path: Path) -> None:
        body = "import sys; sys.stdout.write('z' * 100); sys.stdout.flush()"
        cmd = _write_script(tmp_path, "default.py", body)
        result = run_command(cmd, working_directory=tmp_path)
        assert result.exit_status == 0
        assert len(result.stdout) >= 100
        assert result.truncated is False

    def test_bounded_capture_does_not_misclassify(self, tmp_path: Path) -> None:
        body = (
            "import sys\n"
            "sys.stdout.write('a' * 8000)\n"
            "sys.stdout.flush()\n"
            "sys.exit(2)\n"
        )
        cmd = _write_script(tmp_path, "fail_noisy.py", body)
        result = run_command(
            cmd, working_directory=tmp_path, max_output_bytes=512
        )
        assert result.exit_status == 2
        assert result.classification == Classification.FAILURE
        assert result.truncated is True


class TestDiagnosticLog:
    def test_log_dir_writes_full_stream(self, tmp_path: Path) -> None:
        body = "print('full-stream-marker')"
        cmd = _write_script(tmp_path, "ok.py", body)
        log_dir = subprocess_log_dir(tmp_path)
        result = run_command(
            cmd,
            working_directory=tmp_path,
            component="agent",
            run_id="run-1",
            log_dir=log_dir,
        )
        assert result.log_path is not None
        log = Path(result.log_path)
        assert log.exists()
        assert "full-stream-marker" in log.read_text()
        assert log.name == "agent-run-1.log"

    def test_log_path_layout(self, tmp_path: Path) -> None:
        path = subprocess_log_path(tmp_path, "verify", "run-1", iteration=3)
        assert path == tmp_path / ".sisyphusfy" / "logs" / "verify-run-1-i3.log"

    def test_no_log_dir_leaves_log_path_empty(self, tmp_path: Path) -> None:
        body = "pass"
        cmd = _write_script(tmp_path, "ok.py", body)
        result = run_command(cmd, working_directory=tmp_path, component="agent")
        assert result.log_path is None

    def test_log_records_classification_and_command(self, tmp_path: Path) -> None:
        body = "import sys; sys.exit(3)"
        cmd = _write_script(tmp_path, "bad.py", body)
        log_dir = subprocess_log_dir(tmp_path)
        result = run_command(
            cmd,
            working_directory=tmp_path,
            component="verify",
            run_id="r-1",
            log_dir=log_dir,
        )
        log = Path(result.log_path).read_text()
        assert "classification: failure" in log
        assert "bad.py" in log

    def test_log_retention_bounds_total_files(self, tmp_path: Path) -> None:
        log_dir = subprocess_log_dir(tmp_path)
        for i in range(6):
            write_subprocess_log(
                tmp_path,
                component="agent",
                run_id=f"run-{i}",
                result=run_command(
                    [_write_script(tmp_path, f"ok{i}.py", "pass")[0],
                     str(tmp_path / f"ok{i}.py")],
                    working_directory=tmp_path,
                ),
            )
        # 6 logs across 1 component
        assert len(list(log_dir.glob("*.log"))) == 6
        from sisyphusfy.diagnostics import prune_subprocess_logs

        prune_subprocess_logs(log_dir, retention=3)
        remaining = sorted(p.name for p in log_dir.glob("*.log"))
        assert len(remaining) == 3


class TestCommandNotFound:
    def test_missing_executable_returns_command_not_found(
        self, tmp_path: Path
    ) -> None:
        result = run_command(
            ["definitely-not-a-real-binary-xyz-123"],
            working_directory=tmp_path,
        )
        assert result.classification == Classification.COMMAND_NOT_FOUND
        assert result.exit_status == 127
        assert result.error
        assert "not found" in result.stderr


class TestTimeoutAndInterrupt:
    def test_timeout_classification_preserved(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "slow.py", "import time; time.sleep(10)")
        result = run_command(cmd, working_directory=tmp_path, timeout=0.1)
        assert result.timed_out is True
        assert result.classification == Classification.TIMEOUT

    @_POSIX
    def test_descendant_is_stopped_on_timeout(self, tmp_path: Path) -> None:
        child_pid_path = tmp_path / "child.pid"
        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import os
            import sys
            import time
            from pathlib import Path
            pid = os.fork()
            if pid == 0:
                Path({str(child_pid_path)!r}).write_text(str(os.getpid()))
                time.sleep(30)
                os._exit(0)
            _, status = os.waitpid(pid, 0)
            sys.exit(status >> 8)
            """,
        )
        start = time.monotonic()
        result = run_command(cmd, working_directory=tmp_path, timeout=0.4)
        elapsed = time.monotonic() - start
        assert result.timed_out is True
        assert result.classification == Classification.TIMEOUT
        assert elapsed < 10.0

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not child_pid_path.exists():
            time.sleep(0.05)
        assert child_pid_path.exists()
        assert not _pid_alive(
            int(child_pid_path.read_text().strip())
        )


class TestProgressPreservation:
    def test_on_output_callback_receives_lines(self, tmp_path: Path) -> None:
        body = (
            "import sys\n"
            "print('line1')\n"
            "print('line2')\n"
        )
        cmd = _write_script(tmp_path, "lines.py", body)
        seen: list[str] = []

        def collect(text: str) -> None:
            seen.append(text)

        result = run_command(
            cmd, working_directory=tmp_path, on_output=collect
        )
        assert result.exit_status == 0
        assert any("line1" in line for line in seen)
        assert any("line2" in line for line in seen)

    def test_heartbeat_fires_on_silent_command(self, tmp_path: Path) -> None:
        body = "import time; time.sleep(0.6)"
        cmd = _write_script(tmp_path, "silent.py", body)
        beats: list[tuple[float, float]] = []

        def on_beat(elapsed: float, idle: float) -> None:
            beats.append((elapsed, idle))

        run_command(
            cmd,
            working_directory=tmp_path,
            timeout=2.0,
            heartbeat_interval=0.1,
            on_heartbeat=on_beat,
        )
        assert beats, "no heartbeats captured for a silent 0.6s command"


class TestBoundOutputHelper:
    def test_under_limit_keeps_text(self) -> None:
        text, truncated = bound_output("hello", limit=10)
        assert text == "hello"
        assert truncated is False

    def test_over_limit_truncates(self) -> None:
        text, truncated = bound_output("x" * 20, limit=10)
        assert text == "x" * 10
        assert truncated is True


@_POSIX
class TestWorkflowAndHookShareThePrimitive:
    """Workflow checks and hooks go through the same subprocess primitive."""

    def test_workflow_descendant_reaped_on_timeout(self, tmp_path: Path) -> None:
        """A child forked by the workflow check is reaped by the runner timeout."""
        from sisyphusfy.workflows import ExternalCommandAdapter, WorkflowError

        child_pid_path = tmp_path / "child.pid"
        cmd = _write_script(
            tmp_path,
            "wf.py",
            f"""\
            import os
            import sys
            import time
            from pathlib import Path
            pid = os.fork()
            if pid == 0:
                Path({str(child_pid_path)!r}).write_text(str(os.getpid()))
                time.sleep(30)
                os._exit(0)
            _, status = os.waitpid(pid, 0)
            sys.exit(status >> 8)
            """,
        )
        adapter = ExternalCommandAdapter(
            check_command=cmd, timeout=0.4, working_directory=str(tmp_path)
        )
        start = time.monotonic()
        with pytest.raises(WorkflowError, match="timed out"):
            adapter.is_complete()
        elapsed = time.monotonic() - start
        assert elapsed < 10.0

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not child_pid_path.exists():
            time.sleep(0.05)
        assert child_pid_path.exists()
        assert not _pid_alive(
            int(child_pid_path.read_text().strip())
        )

    def test_hook_reports_command_not_found(self, tmp_path: Path) -> None:
        from sisyphusfy.hooks import (
            HookConfig,
            HookStatus,
            HookType,
            run_hook,
        )

        config = HookConfig(
            hook_type=HookType.ARCHIVE,
            command=["definitely-not-a-real-binary-xyz-123"],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert result.error and "not found" in result.error

    def test_hook_reports_timeout(self, tmp_path: Path) -> None:
        from sisyphusfy.hooks import (
            HookConfig,
            HookStatus,
            HookType,
            run_hook,
        )

        cmd = _write_script(tmp_path, "slow.py", "import time; time.sleep(30)")
        config = HookConfig(
            hook_type=HookType.ARCHIVE, command=cmd, enabled=True
        )
        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert result.error and "timed out" in result.error

    def test_hook_descendant_reaped_on_timeout(self, tmp_path: Path) -> None:
        """A child forked by the hook command is reaped by the runner timeout."""
        from sisyphusfy.hooks import (
            HookConfig,
            HookStatus,
            HookType,
            run_hook,
        )

        child_pid_path = tmp_path / "child.pid"
        cmd = _write_script(
            tmp_path,
            "hook.py",
            f"""\
            import os
            import sys
            import time
            from pathlib import Path
            pid = os.fork()
            if pid == 0:
                Path({str(child_pid_path)!r}).write_text(str(os.getpid()))
                time.sleep(30)
                os._exit(0)
            _, status = os.waitpid(pid, 0)
            sys.exit(status >> 8)
            """,
        )
        config = HookConfig(
            hook_type=HookType.ARCHIVE,
            command=cmd,
            enabled=True,
            working_directory=str(tmp_path),
        )
        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert result.error and "timed out" in result.error

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not child_pid_path.exists():
            time.sleep(0.05)
        assert child_pid_path.exists()
        assert not _pid_alive(
            int(child_pid_path.read_text().strip())
        )
