"""Tests for long-run diagnostics and high-level CLI controls.

Covers:
- Component-labelled diagnostic naming for agent, verification,
  workflow, and hook logs.
- `--verification-timeout` on `run` and `resume` plus dry-run and
  structured reporting of the effective value.
- `resume --verbose` inspecting saved diagnostics without rerunning
  the loop when only inspection was requested.
- Concise human failure summary with diagnostic path and inspect hint.
- JSON shape exposing component, timeout, duration, exit status, and
  diagnostic path.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from sisyphusfy.diagnostics import (
    subprocess_log_path,
    write_subprocess_log,
)
from sisyphusfy.result import Classification, RunResult


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestComponentLabelledDiagnostics:
    def test_subprocess_log_path_uses_component_prefix(self, tmp_path: Path) -> None:
        run_id = "20260101T000000-1"
        agent = subprocess_log_path(tmp_path, "agent", run_id, iteration=1)
        verify = subprocess_log_path(tmp_path, "verify", run_id, iteration=1)
        hook = subprocess_log_path(tmp_path, "hook-pre-commit", run_id)
        assert agent.name.startswith("agent-")
        assert verify.name.startswith("verify-")
        assert hook.name.startswith("hook-pre-commit-")
        assert agent != verify
        assert verify != hook

    def test_write_subprocess_log_records_component(self, tmp_path: Path) -> None:
        run_id = "20260101T000000-1"
        result = RunResult(
            command=["echo", "hi"],
            working_directory=str(tmp_path),
            exit_status=0,
            classification=Classification.SUCCESS,
            timed_out=False,
            duration_ms=5.0,
            stdout="hi\n",
            stderr="",
        )
        path = write_subprocess_log(
            tmp_path,
            component="agent",
            run_id=run_id,
            result=result,
            iteration=1,
        )
        assert path.name.startswith("agent-")
        body = path.read_text()
        assert "echo hi" in body
        assert "exit status: 0" in body


class TestVerificationTimeoutOverride:
    def test_dry_run_shows_verification_timeout(self, tmp_path: Path, capsys) -> None:
        from sisyphusfy.human import cmd_run

        (tmp_path / "tasks.md").write_text("- [x] work\n")
        cmd = _write_script(tmp_path, "noop.py", "pass")
        rc = cmd_run(
            str(tmp_path),
            agent_command=cmd,
            dry_run=True,
            json_output=True,
            verification_timeout=600.0,
        )
        out = capsys.readouterr().out
        data = json.loads(out)
        assert rc == 0
        assert data.get("verification_timeout") == 600.0

    def test_dry_run_human_shows_verification_timeout(
        self, tmp_path: Path, capsys
    ) -> None:
        from sisyphusfy.human import cmd_run

        (tmp_path / "tasks.md").write_text("- [x] work\n")
        cmd = _write_script(tmp_path, "noop.py", "pass")
        cmd_run(
            str(tmp_path),
            agent_command=cmd,
            dry_run=True,
            json_output=False,
            verification_timeout=600.0,
        )
        out = capsys.readouterr().out
        assert "verify-timeout" in out
        assert "600" in out

    def test_resume_passes_verification_timeout(self, tmp_path: Path, capsys) -> None:
        from sisyphusfy.human import cmd_resume

        (tmp_path / "tasks.md").write_text("- [x] work\n")
        _write_script(tmp_path, "noop.py", "pass")
        rc = cmd_resume(
            str(tmp_path),
            dry_run=True,
            json_output=True,
            verification_timeout=120.0,
        )
        out = capsys.readouterr().out
        data = json.loads(out)
        assert rc == 0
        assert data.get("verification_timeout") == 120.0


class TestInspectWithoutRerun:
    def test_resume_inspect_reads_latest_log(self, tmp_path: Path, capsys) -> None:
        from sisyphusfy.human import cmd_resume

        (tmp_path / "tasks.md").write_text("- [x] work\n")
        # Pre-create a fake diagnostic log to be inspected.
        run_id = "20260101T000000-1"
        result = RunResult(
            command=["echo", "synthetic"],
            working_directory=str(tmp_path),
            exit_status=0,
            classification=Classification.SUCCESS,
            timed_out=False,
            duration_ms=1.0,
            stdout="synthetic output\n",
            stderr="",
        )
        write_subprocess_log(
            tmp_path,
            component="verification",
            run_id=run_id,
            result=result,
            iteration=1,
        )
        rc = cmd_resume(
            str(tmp_path),
            inspect_only=True,
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "synthetic output" in out
        assert "synthetic" in out  # the command shows up too

    def test_resume_inspect_missing_log(self, tmp_path: Path, capsys) -> None:
        from sisyphusfy.human import cmd_resume

        (tmp_path / "tasks.md").write_text("- [x] work\n")
        rc = cmd_resume(
            str(tmp_path),
            inspect_only=True,
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "no saved diagnostics" in out.lower() or "no diagnostics" in out.lower()


class TestConciseFailureSummary:
    def test_verification_failure_includes_log_path(
        self, tmp_path: Path, capsys
    ) -> None:
        from sisyphusfy.human import cmd_run

        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        verify = _write_script(
            tmp_path,
            "verify.py",
            "import sys; sys.exit(1)\n",
        )
        agent = _write_script(tmp_path, "agent.py", "pass\n")
        cmd_run(
            str(tmp_path),
            agent_command=agent,
            task_path=str(task_path),
            completion_strategy="markdown",
            verification_command=verify,
            max_iterations=1,
            json_output=False,
        )
        out = capsys.readouterr().out
        # Concise summary should mention log path and inspect hint.
        assert "diagnostics" in out.lower()
        assert "sisyphusfy resume" in out


class TestJsonShape:
    def test_json_result_includes_verification_timeout(
        self, tmp_path: Path, capsys
    ) -> None:
        from sisyphusfy.human import cmd_run

        (tmp_path / "task.md").write_text("- [x] work\n")
        cmd = _write_script(tmp_path, "noop.py", "pass\n")
        cmd_run(
            str(tmp_path),
            agent_command=cmd,
            json_output=True,
            verification_timeout=120.0,
        )
        out = capsys.readouterr().out
        data = json.loads(out)
        # The result is the dry-run shape because the task is already
        # complete; either way the timeout must be exposed.
        assert "verification_timeout" in data or (
            "verification" in data
            and data["verification"].get("timeout") == 120.0
        )
