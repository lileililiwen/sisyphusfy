"""Tests for the loop CLI subcommand."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from sisyphusfy.cli import main


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestLoopCLI:
    def test_loop_basic(self, tmp_path: Path, capsys) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")

        cmd = _write_script(
            tmp_path,
            "noop.py",
            "pass",
        )

        argv = [
            "loop",
            "--task-path", str(task_path),
            "--working-directory", str(tmp_path),
            "--completion-strategy", "markdown",
            "--max-iterations", "1",
            "--",
        ] + cmd

        with __import__("pytest").raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0

    def test_loop_json_output(self, tmp_path: Path, capsys) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")

        cmd = _write_script(
            tmp_path,
            "noop.py",
            "pass",
        )

        argv = [
            "loop",
            "--task-path", str(task_path),
            "--working-directory", str(tmp_path),
            "--completion-strategy", "markdown",
            "--max-iterations", "1",
            "--json",
            "--",
        ] + cmd

        with __import__("pytest").raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "stop_reason" in data
        assert "iterations" in data
        assert "run_records" in data

    def test_loop_with_handoff(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")
        handoff_path = tmp_path / "HANDOFF.md"
        handoff_path.write_text("handoff\n")

        cmd = _write_script(
            tmp_path,
            "noop.py",
            "pass",
        )

        argv = [
            "loop",
            "--task-path", str(task_path),
            "--handoff-path", str(handoff_path),
            "--working-directory", str(tmp_path),
            "--completion-strategy", "markdown",
            "--max-iterations", "1",
            "--",
        ] + cmd

        with __import__("pytest").raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0

    def test_loop_with_verification(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")

        cmd = _write_script(
            tmp_path,
            "noop.py",
            "pass",
        )

        verify_cmd = _write_script(
            tmp_path,
            "verify.py",
            "pass",
        )

        argv = [
            "loop",
            "--task-path", str(task_path),
            "--working-directory", str(tmp_path),
            "--verification-command",
        ] + verify_cmd + [
            "--completion-strategy", "markdown",
            "--max-iterations", "1",
            "--",
        ] + cmd

        with __import__("pytest").raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0

    def test_loop_missing_task_path_fails(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path,
            "noop.py",
            "pass",
        )

        argv = [
            "loop",
            "--max-iterations", "1",
            "--",
        ] + cmd

        with __import__("pytest").raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code != 0

    def test_loop_no_command_fails(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")

        argv = [
            "loop",
            "--task-path", str(task_path),
            "--max-iterations", "1",
        ]

        with __import__("pytest").raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code != 0
