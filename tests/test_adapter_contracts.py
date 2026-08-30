"""Fake-executable OpenCode and CodeBuddy adapter contract tests."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.adapters import (
    AdapterConfig,
    CodeBuddyAdapter,
    OpenCodeAdapter,
    resolve_adapter,
)


def _write_capture_script(tmp: Path, name: str) -> list[str]:
    """Write a script that captures argv and stdin to a file."""
    capture = tmp / f"{name}.log"
    script = tmp / name
    script.write_text(
        textwrap.dedent(f"""\
        import sys
        log = open("{capture}", "w")
        log.write("argv:" + repr(sys.argv[1:]) + "\\n")
        stdin_data = sys.stdin.read()
        log.write("stdin:" + repr(stdin_data) + "\\n")
        log.close()
        """)
    )
    script.chmod(0o755)
    return [sys.executable, str(script)], capture


class TestOpenCodeContract:
    def test_opencode_uses_noninteractive_run(self, tmp_path: Path) -> None:
        adapter = OpenCodeAdapter(model="test-model")
        cmd = adapter.build_command("/tmp/work", "test prompt")
        assert cmd[0] == "opencode"
        assert cmd[1] == "run"
        assert "-c" not in cmd
        assert "-s" not in cmd

    def test_opencode_passes_model(self, tmp_path: Path) -> None:
        adapter = OpenCodeAdapter(model="test-model")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert "--model" in cmd
        assert "test-model" in cmd

    def test_opencode_passes_prompt_as_arg(self, tmp_path: Path) -> None:
        adapter = OpenCodeAdapter()
        cmd = adapter.build_command("/tmp/work", "hello world")
        assert "hello world" in cmd

    def test_opencode_fake_executable_captures_argv(self, tmp_path: Path) -> None:
        script, capture = _write_capture_script(tmp_path, "fake_opencode")
        adapter = OpenCodeAdapter(model="gpt-4")
        cmd = adapter.build_command(str(tmp_path), "do the work")

        result_cmd = script + cmd[1:]
        import subprocess
        subprocess.run(result_cmd, cwd=str(tmp_path), check=False)

        log = capture.read_text()
        assert "argv:" in log
        assert "'--model'" in log
        assert "'gpt-4'" in log
        assert "'do the work'" in log

    def test_opencode_fake_executable_captures_stdin(self, tmp_path: Path) -> None:
        script, capture = _write_capture_script(tmp_path, "fake_opencode_stdin")
        adapter = OpenCodeAdapter()
        cmd = adapter.build_command(str(tmp_path))

        prompt = "read this prompt"
        result_cmd = script + cmd[1:]
        import subprocess
        subprocess.run(
            result_cmd,
            cwd=str(tmp_path),
            input=(prompt + "\n").encode(),
            check=False,
        )

        log = capture.read_text()
        assert "stdin:" in log
        assert "read this prompt" in log


class TestCodeBuddyContract:
    def test_codebuddy_uses_noninteractive_p_flag(self, tmp_path: Path) -> None:
        adapter = CodeBuddyAdapter(model="test-model")
        cmd = adapter.build_command("/tmp/work", "test prompt")
        assert cmd[0] == "codebuddy"
        assert cmd[1] == "-p"
        assert "-c" not in cmd

    def test_codebuddy_passes_model(self, tmp_path: Path) -> None:
        adapter = CodeBuddyAdapter(model="test-model")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert "--model" in cmd
        assert "test-model" in cmd

    def test_codebuddy_passes_prompt(self, tmp_path: Path) -> None:
        adapter = CodeBuddyAdapter()
        cmd = adapter.build_command("/tmp/work", "hello world")
        assert "hello world" in cmd

    def test_codebuddy_fake_executable_captures_argv(self, tmp_path: Path) -> None:
        script, capture = _write_capture_script(tmp_path, "fake_codebuddy")
        adapter = CodeBuddyAdapter(model="claude-3")
        cmd = adapter.build_command(str(tmp_path), "do the work")

        result_cmd = script + cmd[1:]
        import subprocess
        subprocess.run(result_cmd, cwd=str(tmp_path), check=False)

        log = capture.read_text()
        assert "argv:" in log
        assert "'--model'" in log
        assert "'claude-3'" in log
        assert "'do the work'" in log

    def test_codebuddy_fake_executable_captures_stdin(self, tmp_path: Path) -> None:
        script, capture = _write_capture_script(tmp_path, "fake_codebuddy_stdin")
        adapter = CodeBuddyAdapter()
        cmd = adapter.build_command(str(tmp_path))

        prompt = "analyze this"
        result_cmd = script + cmd[1:]
        import subprocess
        subprocess.run(
            result_cmd,
            cwd=str(tmp_path),
            input=(prompt + "\n").encode(),
            check=False,
        )

        log = capture.read_text()
        assert "stdin:" in log
        assert "analyze this" in log


class TestResolveAdapterContracts:
    def test_resolve_opencode_produces_correct_command(self, tmp_path: Path) -> None:
        config = AdapterConfig(name="opencode", model="gpt-4")
        adapter = resolve_adapter(config)
        cmd = adapter.build_command(str(tmp_path), "test")
        assert cmd[0] == "opencode"
        assert cmd[1] == "run"
        assert "--model" in cmd

    def test_resolve_codebuddy_produces_correct_command(self, tmp_path: Path) -> None:
        config = AdapterConfig(name="codebuddy", model="claude-3")
        adapter = resolve_adapter(config)
        cmd = adapter.build_command(str(tmp_path), "test")
        assert cmd[0] == "codebuddy"
        assert cmd[1] == "-p"
        assert "--model" in cmd
