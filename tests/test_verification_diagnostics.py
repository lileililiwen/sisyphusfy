"""Tests for verification diagnostics: bounded evidence, logs, and output."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

from sisyphusfy.cli import main
from sisyphusfy.diagnostics import (
    bound_output,
    make_run_id,
    prune_verification_logs,
    read_verification_log,
    verification_log_dir,
    verification_log_path,
    write_verification_log,
)
from sisyphusfy.human import cmd_doctor, cmd_run
from sisyphusfy.loop import (
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    run_loop,
)
from sisyphusfy.result import Classification, RunResult

VERIFIER_STDOUT = "VERIFIER_STDOUT_MARKER"
VERIFIER_STDERR = "VERIFIER_STDERR_MARKER"


def _script(tmp_path: Path, name: str, body: str) -> list[str]:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


def _failing_verifier(tmp_path: Path) -> list[str]:
    return _script(
        tmp_path,
        "verify.py",
        f"""\
        import sys
        print("{VERIFIER_STDOUT}")
        print("{VERIFIER_STDERR}", file=sys.stderr)
        sys.exit(1)
        """,
    )


class TestDiagnosticLogs:
    def _result(self, stdout: str = "out", stderr: str = "err") -> RunResult:
        return RunResult(
            command=["verify", "--all"],
            exit_status=1,
            classification=Classification.FAILURE,
            stdout=stdout,
            stderr=stderr,
            working_directory="/project",
            duration_ms=12.5,
            env={"SECRET_TOKEN": "must-not-be-logged"},
        )

    def test_log_contains_full_streams(self, tmp_path: Path) -> None:
        path = write_verification_log(tmp_path, "run-1", 2, self._result())
        content = path.read_text()
        assert path.name == "verification-run-1-i2.log"
        assert "verify --all" in content
        assert "classification: failure" in content
        assert "out" in content
        assert "err" in content
        assert "SECRET_TOKEN" not in content

    def test_log_lives_inside_the_project(self, tmp_path: Path) -> None:
        assert verification_log_dir(tmp_path) == tmp_path / ".sisyphusfy" / "logs"
        assert verification_log_path(tmp_path, "run-1", 1).parent == verification_log_dir(
            tmp_path
        )

    def test_run_id_identifies_a_run(self) -> None:
        assert make_run_id(0.0) != make_run_id(1.0)

    def test_retention_bounds_the_log_directory(self, tmp_path: Path) -> None:
        for iteration in range(6):
            write_verification_log(tmp_path, "run-1", iteration, self._result())
        assert len(list(verification_log_dir(tmp_path).glob("*.log"))) == 6

        prune_verification_logs(verification_log_dir(tmp_path), retention=3)
        remaining = sorted(p.name for p in verification_log_dir(tmp_path).glob("*.log"))
        assert remaining == [
            "verification-run-1-i3.log",
            "verification-run-1-i4.log",
            "verification-run-1-i5.log",
        ]

    def test_read_missing_log(self, tmp_path: Path) -> None:
        assert read_verification_log(tmp_path / "nope.log") is None

    def test_output_is_bounded(self) -> None:
        text, truncated = bound_output("x" * 10, limit=10)
        assert text == "x" * 10
        assert truncated is False
        text, truncated = bound_output("x" * 11, limit=10)
        assert text == "x" * 10
        assert truncated is True


class TestLoopRetainsEvidence:
    def _config(self, tmp_path: Path, **overrides) -> LoopConfig:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent = _script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            Path(sys.argv[1]).write_text("- [x] done\\n")
            """,
        )
        config = LoopConfig(
            agent_command=agent + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=2,
            completion_strategy=MarkdownCheckboxCompletion(),
        )
        for key, value in overrides.items():
            setattr(config, key, value)
        return config

    def test_failed_verification_retains_evidence_and_log(self, tmp_path: Path) -> None:
        config = self._config(tmp_path, verification_command=_failing_verifier(tmp_path))
        result = run_loop(config)
        assert result.stop_reason is LoopStopReason.VERIFICATION_FAILED

        evidence = result.verification
        assert evidence is not None
        assert evidence.status == "failure"
        assert evidence.exit_status == 1
        assert evidence.timed_out is False
        assert evidence.stdout == VERIFIER_STDOUT + "\n"
        assert evidence.stderr == VERIFIER_STDERR + "\n"
        assert evidence.log_path is not None

        log = Path(evidence.log_path)
        assert log.exists()
        assert VERIFIER_STDOUT in log.read_text()
        assert VERIFIER_STDERR in log.read_text()
        assert result.to_dict()["verification"]["status"] == "failure"

    def test_evidence_output_is_bounded(self, tmp_path: Path) -> None:
        verifier = _script(
            tmp_path,
            "verify.py",
            """\
            import sys
            print("x" * 5000)
            sys.exit(1)
            """,
        )
        config = self._config(tmp_path, verification_command=verifier)
        result = run_loop(config)
        assert result.verification is not None
        assert len(result.verification.stdout) <= 2000
        assert result.verification.stdout_truncated is True
        assert result.verification.log_path is not None
        assert "x" * 5000 in Path(result.verification.log_path).read_text()

    def test_timeout_retains_evidence(self, tmp_path: Path) -> None:
        verifier = _script(
            tmp_path,
            "verify.py",
            """\
            import time
            time.sleep(30)
            """,
        )
        config = self._config(
            tmp_path, verification_command=verifier, verification_timeout=0.1
        )
        result = run_loop(config)
        assert result.stop_reason is LoopStopReason.TIMEOUT
        assert result.verification is not None
        assert result.verification.timed_out is True
        assert result.verification.log_path is not None

    def test_missing_verifier_retains_evidence(self, tmp_path: Path) -> None:
        config = self._config(
            tmp_path, verification_command=["definitely-not-a-real-command-xyz"]
        )
        result = run_loop(config)
        assert result.stop_reason is LoopStopReason.COMMAND_NOT_FOUND
        assert result.verification is not None
        assert result.verification.status == "command_not_found"

    def test_source_and_detector_are_recorded(self, tmp_path: Path) -> None:
        config = self._config(
            tmp_path,
            verification_command=_failing_verifier(tmp_path),
            verification_source="discovered",
            verification_detector="dotnet",
        )
        result = run_loop(config)
        assert result.verification is not None
        assert result.verification.source == "discovered"
        assert result.verification.detector == "dotnet"

    def test_dry_run_writes_no_diagnostics(self, tmp_path: Path) -> None:
        config = self._config(
            tmp_path,
            verification_command=_failing_verifier(tmp_path),
            dry_run=True,
        )
        result = run_loop(config)
        assert result.verification is None
        assert not verification_log_dir(tmp_path).exists()

    def test_no_verification_retains_no_evidence(self, tmp_path: Path) -> None:
        result = run_loop(self._config(tmp_path))
        assert result.stop_reason is LoopStopReason.COMPLETE
        assert result.verification is None


class _FakeProject:
    """A project configured with the generic adapter and a fake agent binary."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agent = tmp_path / "generic"
        agent.write_text(
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                from pathlib import Path
                Path("tasks.md").write_text("- [x] done\\n")
                """
            )
        )
        agent.chmod(0o755)
        (tmp_path / "tasks.md").write_text("- [ ] work\n")
        monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
        self.path = tmp_path

    def configure(self, verification_command: list[str] | None = None) -> None:
        self.path.joinpath(".sisyphusfy.toml").write_text(
            'adapter = "generic"\n'
            + (
                f"verification_command = {json.dumps(verification_command)}\n"
                if verification_command
                else ""
            )
        )


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _FakeProject:
    return _FakeProject(tmp_path, monkeypatch)


class TestConciseFailureOutput:
    def test_failure_prints_verifier_status_log_path_and_resume(
        self, project: _FakeProject, capsys
    ) -> None:
        project.configure(_failing_verifier(project.path))
        code = cmd_run(str(project.path))
        out = capsys.readouterr().out

        assert code == 1
        assert "verification failed:" in out
        assert "verify.py" in out
        assert "diagnostics:" in out
        assert "resume with: sisyphusfy resume" in out
        assert VERIFIER_STDOUT not in out
        assert VERIFIER_STDERR not in out

    def test_verbose_prints_saved_diagnostics(self, project: _FakeProject, capsys) -> None:
        project.configure(_failing_verifier(project.path))
        cmd_run(str(project.path), verbose=True)
        out = capsys.readouterr().out
        assert VERIFIER_STDOUT in out
        assert VERIFIER_STDERR in out

    def test_verbose_without_verification_is_explained(
        self, project: _FakeProject, capsys
    ) -> None:
        project.configure()
        cmd_run(str(project.path), verbose=True)
        out = capsys.readouterr().out
        assert "no verification diagnostics were captured" in out

    def test_verbose_flag_reaches_the_cli(self, project: _FakeProject, capsys) -> None:
        project.configure(_failing_verifier(project.path))
        with pytest.raises(SystemExit) as exc_info:
            main(["run", "-d", str(project.path), "--verbose"])
        assert exc_info.value.code == 1
        assert VERIFIER_STDOUT in capsys.readouterr().out

    def test_json_reports_verification_metadata(self, project: _FakeProject, capsys) -> None:
        project.configure(_failing_verifier(project.path))
        cmd_run(str(project.path), json_output=True)
        data = json.loads(capsys.readouterr().out.strip())
        verification = data["verification"]
        assert verification["source"] == "configured"
        assert verification["status"] == "failure"
        assert verification["exit_status"] == 1
        assert verification["timed_out"] is False
        assert Path(verification["log_path"]).exists()

    def test_unavailable_verifier_is_reported(self, project: _FakeProject, capsys) -> None:
        project.configure()
        code = cmd_run(str(project.path))
        out = capsys.readouterr().out
        assert code == 0
        assert "verification: none found" in out

    def test_unavailable_verifier_in_json(self, project: _FakeProject, capsys) -> None:
        project.configure()
        cmd_run(str(project.path), json_output=True)
        data = json.loads(capsys.readouterr().out.strip())
        assert data["verification"]["status"] == "skipped"
        assert data["verification"]["source"] == "unavailable"
        assert data["verification"]["command"] == []


class TestResolvedVerifierIsExplained:
    def test_doctor_shows_configured_command(self, project: _FakeProject, capsys) -> None:
        project.configure(["pytest", "-q"])
        cmd_doctor(str(project.path))
        out = capsys.readouterr().out
        assert "verification: configured: pytest -q" in out

    def test_doctor_json_includes_resolution(self, project: _FakeProject, capsys) -> None:
        project.configure(["pytest", "-q"])
        cmd_doctor(str(project.path), json_output=True)
        data = json.loads(capsys.readouterr().out.strip())
        assert data["verification"]["source"] == "configured"
        assert data["verification"]["command"] == ["pytest", "-q"]

    def test_doctor_shows_discovered_command(self, project: _FakeProject, capsys) -> None:
        (project.path / "App.sln").write_text("")
        dotnet = project.path / "dotnet"
        dotnet.write_text("#!/bin/sh\nexit 0\n")
        dotnet.chmod(0o755)

        cmd_doctor(str(project.path))
        out = capsys.readouterr().out
        assert "verification: discovered (dotnet): dotnet test App.sln" in out

    def test_doctor_warns_when_nothing_is_found(self, project: _FakeProject, capsys) -> None:
        cmd_doctor(str(project.path))
        out = capsys.readouterr().out
        assert "verification: none found" in out
        assert "no verification command configured or detected" in out

    def test_dry_run_shows_the_resolved_source(self, project: _FakeProject, capsys) -> None:
        project.configure(["pytest", "-q"])
        cmd_run(str(project.path), dry_run=True)
        out = capsys.readouterr().out
        assert "verify:      configured: pytest -q" in out

    def test_dry_run_json_includes_resolution(self, project: _FakeProject, capsys) -> None:
        project.configure(["pytest", "-q"])
        cmd_run(str(project.path), dry_run=True, json_output=True)
        data = json.loads(capsys.readouterr().out.strip())
        assert data["verification"]["source"] == "configured"
