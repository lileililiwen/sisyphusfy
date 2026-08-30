"""Tests for prompt delivery, working directory, and environment propagation."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.runner import run_agent


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestPromptDelivery:
    def test_prompt_sent_via_stdin(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "read.py", "import sys; print(sys.stdin.read().strip())"
        )
        result = run_agent(cmd, working_directory=tmp_path, prompt="hello agent")
        assert result.exit_status == 0
        assert "hello agent" in result.stdout

    def test_prompt_with_shell_metacharacters(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "read.py", "import sys; print(sys.stdin.read().strip())"
        )
        result = run_agent(
            cmd,
            working_directory=tmp_path,
            prompt="echo $HOME && rm -rf / && `whoami`",
        )
        assert result.exit_status == 0
        assert "$HOME" in result.stdout
        assert "rm -rf" in result.stdout

    def test_prompt_with_quotes(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "read.py", "import sys; print(sys.stdin.read().strip())"
        )
        result = run_agent(
            cmd,
            working_directory=tmp_path,
            prompt="she said \"hello\" and 'goodbye'",
        )
        assert result.exit_status == 0
        assert "hello" in result.stdout
        assert "goodbye" in result.stdout

    def test_multiline_prompt(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "read.py", "import sys; print(sys.stdin.read().strip())"
        )
        prompt = "line 1\nline 2\nline 3"
        result = run_agent(cmd, working_directory=tmp_path, prompt=prompt)
        assert result.exit_status == 0
        assert "line 1" in result.stdout
        assert "line 3" in result.stdout

    def test_prompt_none_means_no_stdin(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path,
            "check.py",
            textwrap.dedent("""\
            import sys
            data = sys.stdin.read()
            print(f"len={len(data)}")
        """),
        )
        result = run_agent(cmd, working_directory=tmp_path, prompt=None)
        assert result.exit_status == 0
        assert "len=0" in result.stdout

    def test_result_stores_prompt(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "noop.py", "")
        result = run_agent(cmd, working_directory=tmp_path, prompt="stored prompt")
        assert result.prompt == "stored prompt"


class TestWorkingDirectory:
    def test_command_runs_in_specified_directory(self, tmp_path: Path) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        cmd = _write_script(tmp_path, "cwd.py", "import os; print(os.getcwd())")
        result = run_agent(cmd, working_directory=sub)
        assert result.stdout.strip() == str(sub.resolve())

    def test_working_directory_with_file_access(self, tmp_path: Path) -> None:
        (tmp_path / "marker.txt").write_text("found")
        cmd = _write_script(
            tmp_path,
            "readfile.py",
            "from pathlib import Path; print(Path('marker.txt').read_text())",
        )
        result = run_agent(cmd, working_directory=tmp_path)
        assert "found" in result.stdout

    def test_relative_path_resolved(self, tmp_path: Path) -> None:
        sub = tmp_path / "nested" / "dir"
        sub.mkdir(parents=True)
        cmd = _write_script(tmp_path, "cwd.py", "import os; print(os.getcwd())")
        result = run_agent(cmd, working_directory=sub)
        assert result.working_directory == str(sub.resolve())


class TestEnvironmentPropagation:
    def test_single_env_variable(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "env.py", "import os; print(os.environ.get('MY_VAR', ''))"
        )
        result = run_agent(cmd, working_directory=tmp_path, env={"MY_VAR": "test123"})
        assert "test123" in result.stdout

    def test_multiple_env_variables(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path,
            "env.py",
            textwrap.dedent("""\
            import os
            a = os.environ.get('VAR_A', '')
            b = os.environ.get('VAR_B', '')
            print(f'{a},{b}')
        """),
        )
        result = run_agent(
            cmd, working_directory=tmp_path, env={"VAR_A": "alpha", "VAR_B": "beta"}
        )
        assert "alpha,beta" in result.stdout

    def test_env_additions_merge_with_parent(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "env.py", "import os; print(os.environ.get('PATH', ''))"
        )
        result = run_agent(cmd, working_directory=tmp_path, env={"MY_VAR": "x"})
        assert result.stdout.strip() != ""

    def test_empty_env_dict_preserves_parent(self, tmp_path: Path) -> None:
        cmd = _write_script(
            tmp_path, "env.py", "import os; print(os.environ.get('PATH', 'MISSING'))"
        )
        result = run_agent(cmd, working_directory=tmp_path, env={})
        assert "MISSING" not in result.stdout

    def test_result_stores_env(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "noop.py", "")
        result = run_agent(cmd, working_directory=tmp_path, env={"A": "1", "B": "2"})
        assert result.env == {"A": "1", "B": "2"}
