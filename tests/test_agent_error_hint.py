"""Tests that provider-side agent errors get an agent-specific diagnostic hint."""

from __future__ import annotations

from sisyphusfy.adapters import (
    AgentError,
    CodeBuddyAdapter,
    GenericCommandAdapter,
    OpenCodeAdapter,
)
from sisyphusfy.human import _print_agent_failure
from sisyphusfy.loop import _is_provider_side_error, _parse_agent_error

UNKNOWN_ENVELOPE = """\
Error: {
"name": "UnknownError",
"data": {
"message": "Unexpected server error. Check server logs for details.",
"ref": "err_abc123"
}
}
"""

SPECIFIC_ENVELOPE = """\
Error: {
"name": "RateLimitError",
"data": {
"message": "rate limited, slow down",
"ref": "err_rl99"
}
}
"""


class _Result:
    def __init__(self, stdout: str = "", stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr


class TestDiagnosticHintOnAdapter:
    def test_opencode_hint_names_its_cli(self) -> None:
        assert "opencode run 'hi'" in OpenCodeAdapter().diagnostic_hint()

    def test_codebuddy_hint_names_its_cli(self) -> None:
        assert "codebuddy" in CodeBuddyAdapter().diagnostic_hint()

    def test_generic_hint_uses_the_command(self) -> None:
        hint = GenericCommandAdapter(["myagent", "run"]).diagnostic_hint()
        assert "myagent run 'hi'" in hint


class TestErrorParsingAttachesHint:
    def test_provider_side_error_gets_hint(self) -> None:
        error = _parse_agent_error(OpenCodeAdapter(), _Result(stderr=UNKNOWN_ENVELOPE))
        assert error is not None
        assert error.name == "UnknownError"
        assert error.hint is not None
        assert "opencode run 'hi'" in error.hint

    def test_specific_error_gets_no_hint(self) -> None:
        error = _parse_agent_error(OpenCodeAdapter(), _Result(stderr=SPECIFIC_ENVELOPE))
        assert error is not None
        assert error.name == "RateLimitError"
        assert error.hint is None

    def test_message_only_server_error_gets_hint(self) -> None:
        # The envelope parse may or may not recover a name, but the message still
        # signals a generic server error; detection must treat it as provider-side.
        assert _is_provider_side_error(
            AgentError(message="Unexpected server error. Check server logs for details.")
        )
        assert not _is_provider_side_error(AgentError(message="rate limited, slow down"))


class TestAgentErrorDict:
    def test_hint_omitted_when_absent(self) -> None:
        assert "hint" not in AgentError(name="X").to_dict()

    def test_hint_included_when_set(self) -> None:
        d = AgentError(name="X", hint="run it directly").to_dict()
        assert d["hint"] == "run it directly"


class TestHumanReportShowsHint:
    def test_hint_is_printed(self, capsys) -> None:
        evidence = _FakeEvidence()
        result = _FakeResult(agent_evidence=evidence, agent_error=AgentError(
            name="UnknownError",
            message="Unexpected server error. Check server logs for details.",
            reference="err_abc123",
            hint="Run: opencode run 'hi' --print-logs --log-level DEBUG",
        ))
        _print_agent_failure(result)
        out = capsys.readouterr().out

        assert "[agent] failed: opencode exited with code 1" in out
        assert "[agent] reference: err_abc123" in out
        assert "[agent] this is an agent-CLI/provider error, not a sisyphusfy failure." in out
        assert "[agent] diagnose: Run: opencode run 'hi'" in out

    def test_specific_error_has_no_hint_line(self, capsys) -> None:
        evidence = _FakeEvidence()
        result = _FakeResult(agent_evidence=evidence, agent_error=AgentError(
            name="RateLimitError",
            message="rate limited",
        ))
        _print_agent_failure(result)
        out = capsys.readouterr().out

        assert "[agent] error: rate limited" in out
        assert "not a sisyphusfy failure" not in out


class _FakeEvidence:
    def __init__(self) -> None:
        self.command = ["opencode", "run", "prompt"]
        self.exit_status = 1
        self.log_path = None


class _FakeResult:
    def __init__(self, agent_evidence=None, agent_error=None) -> None:
        self.agent_evidence = agent_evidence
        self.agent_error = agent_error
