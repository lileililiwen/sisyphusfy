"""Tests for human-readable and JSON result output."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from sisyphusfy.cli import main


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [str(path)]


def _run(
    tmp_path: Path,
    capsys,
    *extra_args: str,
    cmd_name: str = "ok.py",
    cmd_body: str = "print('hello')",
) -> None:
    script = _write_script(tmp_path, cmd_name, cmd_body)
    full_args = list(extra_args) + [sys.executable] + script
    try:
        main(full_args)
    except SystemExit:
        pass


class TestHumanOutput:
    def test_success_shows_ok(self, tmp_path: Path, capsys) -> None:
        _run(tmp_path, capsys, "-d", str(tmp_path))
        out = capsys.readouterr().out
        assert "[OK]" in out

    def test_failure_shows_exit_code(self, tmp_path: Path, capsys) -> None:
        _run(
            tmp_path,
            capsys,
            "-d",
            str(tmp_path),
            cmd_name="fail.py",
            cmd_body="import sys; sys.exit(42)",
        )
        out = capsys.readouterr().out
        assert "[exit 42]" in out

    def test_dry_run_shows_command(self, tmp_path: Path, capsys) -> None:
        _run(
            tmp_path,
            capsys,
            "-d",
            str(tmp_path),
            "--dry-run",
            cmd_name="noop.py",
            cmd_body="print('no')",
        )
        out = capsys.readouterr().out
        assert "dry-run:" in out
        assert str(tmp_path) in out

    def test_dry_run_with_prompt(self, tmp_path: Path, capsys) -> None:
        _run(
            tmp_path,
            capsys,
            "-d",
            str(tmp_path),
            "--dry-run",
            "-p",
            "test prompt",
            cmd_name="noop.py",
            cmd_body="",
        )
        out = capsys.readouterr().out
        assert "test prompt" in out

    def test_stdout_displayed(self, tmp_path: Path, capsys) -> None:
        _run(
            tmp_path,
            capsys,
            "-d",
            str(tmp_path),
            cmd_name="out.py",
            cmd_body="print('visible output')",
        )
        out = capsys.readouterr().out
        assert "visible output" in out


class TestJsonOutput:
    def test_json_output_is_valid_json(self, tmp_path: Path, capsys) -> None:
        _run(tmp_path, capsys, "-d", str(tmp_path), "--json")
        out = capsys.readouterr().out.strip()
        data = json.loads(out)
        assert isinstance(data, dict)

    def test_json_contains_required_fields(self, tmp_path: Path, capsys) -> None:
        _run(tmp_path, capsys, "-d", str(tmp_path), "--json")
        data = json.loads(capsys.readouterr().out.strip())
        assert "command" in data
        assert "exit_status" in data
        assert "classification" in data
        assert "duration_ms" in data
        assert "working_directory" in data

    def test_json_success_classification(self, tmp_path: Path, capsys) -> None:
        _run(
            tmp_path,
            capsys,
            "-d",
            str(tmp_path),
            "--json",
            cmd_name="ok.py",
            cmd_body="",
        )
        data = json.loads(capsys.readouterr().out.strip())
        assert data["classification"] == "success"
        assert data["exit_status"] == 0

    def test_json_failure_classification(self, tmp_path: Path, capsys) -> None:
        _run(
            tmp_path,
            capsys,
            "-d",
            str(tmp_path),
            "--json",
            cmd_name="fail.py",
            cmd_body="import sys; sys.exit(7)",
        )
        data = json.loads(capsys.readouterr().out.strip())
        assert data["classification"] == "failure"
        assert data["exit_status"] == 7

    def test_json_dry_run_classification(self, tmp_path: Path, capsys) -> None:
        _run(
            tmp_path,
            capsys,
            "-d",
            str(tmp_path),
            "--json",
            "--dry-run",
            cmd_name="noop.py",
            cmd_body="",
        )
        data = json.loads(capsys.readouterr().out.strip())
        assert data["classification"] == "dry_run"
        assert data["exit_status"] is None

    def test_json_includes_stdout_stderr(self, tmp_path: Path, capsys) -> None:
        _run(
            tmp_path,
            capsys,
            "-d",
            str(tmp_path),
            "--json",
            cmd_name="both.py",
            cmd_body="import sys; print('out'); print('err', file=sys.stderr)",
        )
        data = json.loads(capsys.readouterr().out.strip())
        assert "out" in data["stdout"]
        assert "err" in data["stderr"]


class TestHelpAndErrors:
    def test_help_flag_shows_usage(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "usage:" in out.lower() or "sisyphusfy" in out

    def test_short_help_flag(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["-h"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "usage:" in out.lower() or "sisyphusfy" in out

    def test_no_command_shows_error(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0
        err = capsys.readouterr().err
        assert "No command provided" in err

    def test_help_before_command(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help", "--", "echo", "test"])
        assert exc_info.value.code == 0


class TestSeparatorAndEnv:
    def test_double_dash_separator(self, tmp_path: Path, capsys) -> None:
        script = _write_script(tmp_path, "ok.py", "print('ran')")[0]
        try:
            main(["--dry-run", "--", sys.executable, script])
        except SystemExit:
            pass
        out = capsys.readouterr().out
        assert "dry-run:" in out

    def test_double_dash_with_flags_after(self, tmp_path: Path, capsys) -> None:
        script = _write_script(tmp_path, "ok.py", "print('ran')")[0]
        try:
            main(["-d", str(tmp_path), "--dry-run", "--", sys.executable, script])
        except SystemExit:
            pass
        out = capsys.readouterr().out
        assert "dry-run:" in out

    def test_env_flag_single(self, tmp_path: Path, capsys) -> None:
        script = _write_script(
            tmp_path,
            "env.py",
            "import os; print(os.environ.get('MY_KEY', 'MISSING'))",
        )[0]
        try:
            main(
                [
                    "-e",
                    "MY_KEY=my_value",
                    "-d",
                    str(tmp_path),
                    "--",
                    sys.executable,
                    script,
                ]
            )
        except SystemExit:
            pass
        out = capsys.readouterr().out
        assert "my_value" in out

    def test_env_flag_multiple(self, tmp_path: Path, capsys) -> None:
        script = _write_script(
            tmp_path,
            "env.py",
            "import os; print(os.environ.get('A', ''), os.environ.get('B', ''))",
        )[0]
        try:
            main(
                [
                    "-e",
                    "A=alpha",
                    "-e",
                    "B=beta",
                    "-d",
                    str(tmp_path),
                    "--",
                    sys.executable,
                    script,
                ]
            )
        except SystemExit:
            pass
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "beta" in out

    def test_env_flag_json_output(self, tmp_path: Path, capsys) -> None:
        script = _write_script(tmp_path, "noop.py", "")[0]
        try:
            main(["-e", "X=1", "--json", "--dry-run", "--", sys.executable, script])
        except SystemExit:
            pass
        data = json.loads(capsys.readouterr().out.strip())
        assert data["env"] == {"X": "1"}
