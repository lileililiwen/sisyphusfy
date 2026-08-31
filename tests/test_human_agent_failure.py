"""Human-output tests for a failed agent run."""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

from sisyphusfy.human import cmd_run

ERROR_ENVELOPE = """\
Error: {
"name": "UnknownError",
"data": {
"message": "Unexpected server error. Check server logs for details.",
"ref": "err_cbece906"
}
}
"""

EXPECTED_MESSAGE = "Unexpected server error. Check server logs for details."
EXPECTED_REFERENCE = "err_cbece906"


class _FailingProject:
    """A project whose `generic` adapter fails with a JSON error envelope."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        agent_body: str,
    ) -> None:
        agent = tmp_path / "generic"
        agent.write_text(f"#!{sys.executable}\n{textwrap.dedent(agent_body)}")
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
def failing_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _FailingProject:
    return _FailingProject(
        tmp_path,
        monkeypatch,
        f"""\
import sys
print({ERROR_ENVELOPE!r}, file=sys.stderr)
sys.exit(1)
""",
    )


class TestAgentFailureOutput:
    def test_prints_command_error_reference_and_resume(
        self, failing_project: _FailingProject, capsys
    ) -> None:
        failing_project.configure()
        code = cmd_run(str(failing_project.path))
        out = capsys.readouterr().out

        assert code == 1
        assert "[agent] failed: generic exited with code 1" in out
        assert f"[agent] error: {EXPECTED_MESSAGE}" in out
        assert f"[agent] reference: {EXPECTED_REFERENCE}" in out
        assert "[agent] diagnostics:" in out
        assert "stopped: agent_failed" in out
        assert "resume with: sisyphusfy resume" in out
        # The default result stays concise: raw streams require --verbose.
        assert '"name": "UnknownError"' not in out

    def test_verbose_prints_the_saved_agent_diagnostics(
        self, failing_project: _FailingProject, capsys
    ) -> None:
        failing_project.configure()
        cmd_run(str(failing_project.path), verbose=True)
        out = capsys.readouterr().out

        assert "agent diagnostics:" in out
        assert EXPECTED_REFERENCE in out
        assert "--- stderr ---" in out

    def test_json_reports_the_agent_error(
        self, failing_project: _FailingProject, capsys
    ) -> None:
        failing_project.configure()
        cmd_run(str(failing_project.path), json_output=True)
        data = json.loads(capsys.readouterr().out.strip())

        assert data["stop_reason"] == "agent_failed"
        assert data["agent_error"] == {
            "name": "UnknownError",
            "message": EXPECTED_MESSAGE,
            "reference": EXPECTED_REFERENCE,
        }
        assert data["verification"]["status"] == "skipped"
        assert Path(data["agent_evidence"]["log_path"]).exists()

    def test_the_verifier_never_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        marker = tmp_path / "verify.marker"
        verify = tmp_path / "verify.py"
        verify.write_text(
            textwrap.dedent(f"""\
                from pathlib import Path
                Path({str(marker)!r}).write_text("ran")
                """)
        )
        project = _FailingProject(
            tmp_path,
            monkeypatch,
            """\
            import sys
            sys.exit(1)
            """,
        )
        project.configure(verification_command=[sys.executable, str(verify)])

        code = cmd_run(str(project.path))

        assert code == 1
        assert "stopped: agent_failed" in capsys.readouterr().out
        assert not marker.exists()

    def test_bare_failure_omits_the_error_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        project = _FailingProject(
            tmp_path,
            monkeypatch,
            """\
            import sys
            sys.exit(1)
            """,
        )
        project.configure()

        cmd_run(str(project.path))
        out = capsys.readouterr().out

        assert "[agent] failed: generic exited with code 1" in out
        assert "[agent] diagnostics:" in out
        assert "stopped: agent_failed" in out
        assert "[agent] error:" not in out
        assert "[agent] reference:" not in out
