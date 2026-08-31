"""Tests that commands are rendered with unambiguous quoting.

The agent command is passed as one multi-word argument, so a naive space join
makes it look like a malformed, unquoted command. Every site that displays a
command must instead quote argument boundaries.
"""

from __future__ import annotations

from pathlib import Path

from sisyphusfy.config import VerificationResolution, VerificationSource
from sisyphusfy.diagnostics import read_verification_log, write_verification_log
from sisyphusfy.human import (
    _describe_verification,
    _print_timeout_detail,
    _print_verifier_status,
)
from sisyphusfy.loop import VerificationEvidence
from sisyphusfy.result import Classification, RunResult, format_command

SIMPLE_COMMAND = ["dotnet", "test", "App.sln"]
MULTIWORD_COMMAND = [
    "opencode",
    "run",
    "Read /home/paul/code/openlearning/tasks.md and any handoff at HANDOFF.md. Implement one task.",
]


class TestFormatCommand:
    def test_quotes_a_multiword_argument(self) -> None:
        rendered = format_command(MULTIWORD_COMMAND)
        assert "'" in rendered
        # The whole prompt is one quoted token, not split on spaces.
        assert "Read /home/paul/code/openlearning/tasks.md and any handoff" in rendered
        assert rendered.startswith("opencode run '")

    def test_leaves_a_simple_command_unchanged(self) -> None:
        assert format_command(SIMPLE_COMMAND) == "dotnet test App.sln"

    def test_empty_command_renders_safely(self) -> None:
        assert format_command([]) == ""


class TestDiagnosticLogHeader:
    def test_command_header_shows_argument_boundaries(self, tmp_path: Path) -> None:
        result = RunResult(
            command=MULTIWORD_COMMAND,
            exit_status=1,
            classification=Classification.FAILURE,
            working_directory=str(tmp_path),
        )
        path = write_verification_log(tmp_path, "runid", 1, result)
        log = read_verification_log(path)

        assert log is not None
        assert "command: " in log
        header = next(line for line in log.splitlines() if line.startswith("command: "))
        # The prompt must be one quoted argument, not space-joined words.
        assert "opencode run '" in header


class TestVerificationDescription:
    def test_describe_configured_quotes_command(self) -> None:
        resolution = VerificationResolution(
            command=MULTIWORD_COMMAND,
            source=VerificationSource.CONFIGURED,
        )
        assert "opencode run '" in _describe_verification(resolution)

    def test_describe_discovered_quotes_command(self) -> None:
        resolution = VerificationResolution(
            command=SIMPLE_COMMAND,
            source=VerificationSource.DISCOVERED,
            detector="tox",
        )
        assert _describe_verification(resolution) == "discovered (tox): dotnet test App.sln"


class TestHumanCommandLines:
    def test_timeout_report_quotes_command(self, capsys) -> None:
        evidence = VerificationEvidence(
            command=MULTIWORD_COMMAND,
            working_directory="/tmp",
            exit_status=None,
            status="timeout",
            timed_out=True,
            duration_ms=1000.0,
        )
        _print_timeout_detail("agent", evidence, 30.0)
        out = capsys.readouterr().out

        assert "agent timed out after" in out
        assert "opencode run '" in out

    def test_verifier_status_quotes_command(self, capsys) -> None:
        evidence = VerificationEvidence(
            command=MULTIWORD_COMMAND,
            working_directory="/tmp",
            exit_status=1,
            status="failure",
            timed_out=False,
            duration_ms=1000.0,
        )
        result = _FakeResult(verification=evidence)
        _print_verifier_status(result, "failed")
        out = capsys.readouterr().out

        assert "verification failed: opencode run '" in out


class _FakeResult:
    """Minimal stand-in carrying only what _print_verifier_status reads."""

    def __init__(self, verification: VerificationEvidence | None) -> None:
        self.verification = verification


class TestStructuredOutputUnchanged:
    def test_json_reports_command_as_a_list(self) -> None:
        result = RunResult(
            command=MULTIWORD_COMMAND,
            exit_status=0,
            classification=Classification.SUCCESS,
        )
        payload = result.to_dict()

        assert isinstance(payload["command"], list)
        assert payload["command"] == MULTIWORD_COMMAND
