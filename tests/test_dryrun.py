"""Dry-run test that proves no subprocess starts."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

from sisyphusfy.result import Classification
from sisyphusfy.runner import run_agent


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestDryRun:
    def test_dry_run_returns_dry_run_classification(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "noop.py", "print('should not run')")
        result = run_agent(cmd, working_directory=tmp_path, dry_run=True)
        assert result.classification == Classification.DRY_RUN

    def test_dry_run_does_not_execute_command(self, tmp_path: Path) -> None:
        marker = tmp_path / "marker.txt"
        cmd = _write_script(
            tmp_path, "write.py", f"Path('{marker}').write_text('created')"
        )
        run_agent(cmd, working_directory=tmp_path, dry_run=True)
        assert not marker.exists()

    def test_dry_run_returns_no_exit_status(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "noop.py", "")
        result = run_agent(cmd, working_directory=tmp_path, dry_run=True)
        assert result.exit_status is None

    def test_dry_run_captures_command(self, tmp_path: Path) -> None:
        cmd = ["echo", "hello", "world"]
        result = run_agent(cmd, working_directory=tmp_path, dry_run=True)
        assert result.command == cmd

    def test_dry_run_with_prompt(self, tmp_path: Path) -> None:
        cmd = ["echo", "test"]
        result = run_agent(
            cmd, working_directory=tmp_path, prompt="my prompt", dry_run=True
        )
        assert result.prompt == "my prompt"

    def test_dry_run_with_env(self, tmp_path: Path) -> None:
        cmd = ["echo", "test"]
        result = run_agent(
            cmd, working_directory=tmp_path, env={"A": "1"}, dry_run=True
        )
        assert result.env == {"A": "1"}

    def test_dry_run_with_timeout(self, tmp_path: Path) -> None:
        cmd = ["sleep", "100"]
        result = run_agent(cmd, working_directory=tmp_path, timeout=999, dry_run=True)
        assert result.classification == Classification.DRY_RUN
        assert result.timed_out is False

    def test_dry_run_no_duration(self, tmp_path: Path) -> None:
        cmd = ["echo", "test"]
        result = run_agent(cmd, working_directory=tmp_path, dry_run=True)
        assert result.duration_ms == 0.0

    def test_dry_run_proves_no_subprocess_started(self, tmp_path: Path) -> None:
        cmd = ["nonexistent_command_xyz"]
        with patch("subprocess.run") as mock_run:
            result = run_agent(cmd, working_directory=tmp_path, dry_run=True)
            mock_run.assert_not_called()
        assert result.classification == Classification.DRY_RUN

    def test_dry_run_result_has_working_directory(self, tmp_path: Path) -> None:
        cmd = ["echo", "test"]
        result = run_agent(cmd, working_directory=tmp_path, dry_run=True)
        assert result.working_directory == str(tmp_path.resolve())
