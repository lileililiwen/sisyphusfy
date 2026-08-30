"""Process tests for exit status and timeout classification."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.result import Classification
from sisyphusfy.runner import run_agent


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestSuccessfulExit:
    def test_stdout_captured(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "out.py", "print('hello stdout')")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 0
        assert result.classification == Classification.SUCCESS
        assert "hello stdout" in result.stdout

    def test_stderr_captured(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "err.py", "import sys; print('hello stderr', file=sys.stderr)"
        )
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 0
        assert "hello stderr" in result.stderr

    def test_stdout_and_stderr_captured(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path,
            "both.py",
            textwrap.dedent("""\
            import sys
            print('stdout line')
            print('stderr line', file=sys.stderr)
            print('stdout line 2')
        """),
        )
        result = run_agent(cmd, working_directory=tmp_path)
        assert "stdout line" in result.stdout
        assert "stderr line" in result.stderr

    def test_multiline_output_captured(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "multi.py", "print('line1'); print('line2'); print('line3')"
        )
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 0
        assert "line1\nline2\nline3" in result.stdout

    def test_large_output_captured(self, tmp_path: Path) -> None:
        body = "print('\\n'.join(f'line {i}' for i in range(500)))"
        cmd = _write_script(tmp_path, "big.py", body)
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 0
        assert "line 0" in result.stdout
        assert "line 499" in result.stdout

    def test_exit_status_zero(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "exit0.py", "import sys; sys.exit(0)")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 0
        assert result.timed_out is False

    def test_duration_recorded(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "dur.py", "print('ok')")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.duration_ms > 0

    def test_empty_output(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "silent.py", "")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 0
        assert result.stdout == ""
        assert result.stderr == ""


class TestNonZeroExit:
    def test_exit_status_1(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "exit1.py", "import sys; sys.exit(1)")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 1
        assert result.classification == Classification.FAILURE
        assert result.timed_out is False

    def test_exit_status_42(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "exit42.py", "import sys; sys.exit(42)")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 42
        assert result.classification == Classification.FAILURE

    def test_exit_with_stderr(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path,
            "failerr.py",
            textwrap.dedent("""\
            import sys
            print('error output', file=sys.stderr)
            sys.exit(1)
        """),
        )
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 1
        assert "error output" in result.stderr

    def test_exit_with_stdout_and_stderr(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path,
            "mixed.py",
            textwrap.dedent("""\
            import sys
            print('partial output')
            print('error details', file=sys.stderr)
            sys.exit(2)
        """),
        )
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 2
        assert "partial output" in result.stdout
        assert "error details" in result.stderr


class TestTimeoutClassification:
    def test_timeout_when_exceeds_limit(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "slow.py", "import time; time.sleep(10)")
        result = run_agent(cmd, working_directory=tmp_path, timeout=0.1)
        assert result.timed_out is True
        assert result.classification == Classification.TIMEOUT
        assert (
            result.exit_status == -1
            or result.exit_status is None
            or result.exit_status == -9
        )

    def test_short_timeout_returns_immediately(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "fast.py", "print('ok')")
        result = run_agent(cmd, working_directory=tmp_path, timeout=10.0)
        assert result.timed_out is False
        assert result.classification == Classification.SUCCESS
