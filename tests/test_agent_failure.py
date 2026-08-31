"""Tests for stopping the loop when an agent run fails."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from sisyphusfy.loop import (
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    run_loop,
)

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


def _script(tmp_path: Path, name: str, body: str) -> list[str]:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


def _marker_verifier(tmp_path: Path) -> tuple[list[str], Path]:
    """A verifier that records the fact that it ran."""
    marker = tmp_path / "verify.marker"
    cmd = _script(
        tmp_path,
        "verify.py",
        f"""\
        from pathlib import Path
        Path({str(marker)!r}).write_text("ran")
        """,
    )
    return cmd, marker


def _config(
    tmp_path: Path,
    task_path: Path,
    agent_cmd: list[str],
    **kwargs,
) -> LoopConfig:
    return LoopConfig(
        agent_command=agent_cmd,
        working_directory=str(tmp_path),
        task_path=str(task_path),
        prompt_template="do work",
        max_iterations=2,
        completion_strategy=MarkdownCheckboxCompletion(),
        **kwargs,
    )


class TestStopOnFailure:
    def test_failing_agent_stops_without_model_chain(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            """\
            import sys
            sys.exit(1)
            """,
        )

        result = run_loop(_config(tmp_path, task_path, agent_cmd))

        assert result.stop_reason == LoopStopReason.AGENT_FAILED
        assert result.iterations == 1

    def test_failing_agent_does_not_run_verification(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            """\
            import sys
            sys.exit(1)
            """,
        )
        verify_cmd, marker = _marker_verifier(tmp_path)

        result = run_loop(
            _config(tmp_path, task_path, agent_cmd, verification_command=verify_cmd)
        )

        assert result.stop_reason == LoopStopReason.AGENT_FAILED
        assert result.verification is None
        assert not marker.exists()

    def test_successful_agent_still_verifies(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            Path({str(task_path)!r}).write_text("- [x] done\\n")
            """,
        )
        verify_cmd, marker = _marker_verifier(tmp_path)

        result = run_loop(
            _config(tmp_path, task_path, agent_cmd, verification_command=verify_cmd)
        )

        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.verification is not None
        assert marker.exists()


class TestAgentErrorRecovery:
    def test_error_parsed_from_stderr(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            print({ERROR_ENVELOPE!r}, file=sys.stderr)
            sys.exit(1)
            """,
        )

        result = run_loop(_config(tmp_path, task_path, agent_cmd))

        assert result.agent_error is not None
        assert result.agent_error.name == "UnknownError"
        assert result.agent_error.message == EXPECTED_MESSAGE
        assert result.agent_error.reference == EXPECTED_REFERENCE

    def test_error_parsed_from_stdout(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            print({ERROR_ENVELOPE!r})
            sys.exit(1)
            """,
        )

        result = run_loop(_config(tmp_path, task_path, agent_cmd))

        assert result.agent_error is not None
        assert result.agent_error.message == EXPECTED_MESSAGE
        assert result.agent_error.reference == EXPECTED_REFERENCE

    def test_plain_failure_yields_no_error(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            """\
            import sys
            sys.exit(1)
            """,
        )

        result = run_loop(_config(tmp_path, task_path, agent_cmd))

        assert result.stop_reason == LoopStopReason.AGENT_FAILED
        assert result.agent_error is None

    def test_malformed_envelope_yields_no_error(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            """\
            import sys
            print('Error: {"name": "UnknownError",')
            sys.exit(1)
            """,
        )

        result = run_loop(_config(tmp_path, task_path, agent_cmd))

        assert result.stop_reason == LoopStopReason.AGENT_FAILED
        assert result.agent_error is None


class TestAgentFailureEvidence:
    def test_failure_retains_evidence_and_log(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            print({ERROR_ENVELOPE!r}, file=sys.stderr)
            sys.exit(1)
            """,
        )

        result = run_loop(_config(tmp_path, task_path, agent_cmd))
        evidence = result.agent_evidence

        assert evidence is not None
        assert evidence.exit_status == 1
        assert evidence.timed_out is False
        assert evidence.source == "agent"
        assert evidence.log_path is not None
        assert EXPECTED_REFERENCE in Path(evidence.log_path).read_text()

    def test_failure_json_shape(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            print({ERROR_ENVELOPE!r}, file=sys.stderr)
            sys.exit(1)
            """,
        )

        result = run_loop(_config(tmp_path, task_path, agent_cmd))
        data = result.to_dict()

        assert data["stop_reason"] == "agent_failed"
        assert data["agent_error"] == {
            "name": "UnknownError",
            "message": EXPECTED_MESSAGE,
            "reference": EXPECTED_REFERENCE,
        }
        assert "verification" not in data
        assert json.dumps(data)


class TestClassificationPriority:
    def test_blocked_marker_wins_over_failure(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            """\
            import sys
            print("NEED_PERMISSION: approve the refactor")
            sys.exit(2)
            """,
        )

        result = run_loop(_config(tmp_path, task_path, agent_cmd))

        assert result.stop_reason == LoopStopReason.BLOCKED
        assert result.iterations == 1

    def test_all_retryable_chain_keeps_models_exhausted(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        agent_cmd = _script(
            tmp_path,
            "agent.py",
            """\
            import sys
            print("quota exceeded", file=sys.stderr)
            sys.exit(1)
            """,
        )

        result = run_loop(
            _config(tmp_path, task_path, agent_cmd, model_chain=["model-a", "model-b"])
        )

        assert result.stop_reason == LoopStopReason.MODELS_EXHAUSTED
        assert result.model_attempts == ["model-a", "model-b"]
        assert result.agent_evidence is not None
        assert result.agent_evidence.log_path is not None
