"""Unit tests for command construction and argument preservation."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.result import Classification
from sisyphusfy.runner import run_agent


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    """Write an executable script and return the command to invoke it."""
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestCommandConstruction:
    def test_command_list_is_preserved(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "echo_args.py", "import sys; print(sys.argv[1:])")
        result = run_agent(cmd + ["--flag", "value"], working_directory=tmp_path)
        assert result.command == cmd + ["--flag", "value"]
        assert "--flag" in result.stdout
        assert "value" in result.stdout

    def test_simple_command(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "hello.py", "print('hello')")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.exit_status == 0
        assert result.classification == Classification.SUCCESS
        assert "hello" in result.stdout

    def test_empty_args(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "noargs.py", "print(len(__import__('sys').argv))")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.stdout.strip() == "1"

    def test_special_characters_in_args(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "special.py", "import sys; [print(a) for a in sys.argv[1:]]"
        )
        result = run_agent(
            cmd + ["--msg", "$HOME 'path' \"quoted\""], working_directory=tmp_path
        )
        assert result.exit_status == 0
        assert "$HOME" in result.stdout
        assert "path" in result.stdout

    def test_multiline_command_preserved(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "multi.py", "import sys; print(len(sys.argv))")
        full = cmd + ["line1", "line2", "line3"]
        result = run_agent(full, working_directory=tmp_path)
        assert result.stdout.strip() == "4"  # script + 3 args

    def test_working_directory_is_set(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "cwd.py", "import os; print(os.getcwd())")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.working_directory == str(tmp_path.resolve())
        assert result.stdout.strip() == str(tmp_path.resolve())

    def test_env_variables_passed(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "env.py", "import os; print(os.environ.get('TEST_VAR', ''))"
        )
        result = run_agent(cmd, working_directory=tmp_path, env={"TEST_VAR": "hello"})
        assert "hello" in result.stdout
        assert result.env == {"TEST_VAR": "hello"}

    def test_duration_is_positive(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "fast.py", "print('ok')")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.duration_ms >= 0

    def test_classification_success(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "ok.py", "print('ok')")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.classification == Classification.SUCCESS

    def test_classification_failure(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "fail.py", "import sys; sys.exit(42)")
        result = run_agent(cmd, working_directory=tmp_path)
        assert result.classification == Classification.FAILURE
        assert result.exit_status == 42
