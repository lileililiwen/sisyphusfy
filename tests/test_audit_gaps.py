"""Regression tests for the post-commit audit of 9648b58.

Covers the two behavioral gaps: the low-level external completion check ran in
the caller's current directory, and a missing executable surfaced as an
unhandled exception instead of a structured result.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.hooks import HookConfig, HookType
from sisyphusfy.loop import (
    CompletionCheckError,
    ExternalCommandCompletion,
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    run_loop,
)
from sisyphusfy.result import Classification
from sisyphusfy.runner import run_agent


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


def _cwd_recorder(target: Path, name: str) -> list[str]:
    return _write_script(
        target,
        name,
        f"""\
        from pathlib import Path
        Path({str(target / (name + '.cwd'))!r}).write_text(str(Path.cwd()))
        """,
    )


class TestCompletionCheckWorkingDirectory:
    def test_check_runs_in_selected_working_directory(self, tmp_path, monkeypatch) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "task.md").write_text("- [ ] work\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        config = LoopConfig(
            agent_command=_write_script(project, "agent.py", "pass"),
            working_directory=str(project),
            task_path="task.md",
            prompt_template="do work",
            max_iterations=1,
            completion_strategy=ExternalCommandCompletion(
                check_command=_cwd_recorder(project, "check.py"),
            ),
        )

        monkeypatch.chdir(elsewhere)
        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMPLETE
        recorded = Path((project / "check.py.cwd").read_text())
        assert recorded == project.resolve()

    def test_explicit_check_directory_is_preserved(self, tmp_path, monkeypatch) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "task.md").write_text("- [ ] work\n")
        custom = tmp_path / "custom"
        custom.mkdir()
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        config = LoopConfig(
            agent_command=_write_script(project, "agent.py", "pass"),
            working_directory=str(project),
            task_path="task.md",
            prompt_template="do work",
            max_iterations=1,
            completion_strategy=ExternalCommandCompletion(
                check_command=_cwd_recorder(custom, "check.py"),
                working_directory=str(custom),
            ),
        )

        monkeypatch.chdir(elsewhere)
        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMPLETE
        recorded = Path((custom / "check.py.cwd").read_text())
        assert recorded == custom.resolve()


class TestMissingAgentCommand:
    def test_run_agent_classifies_missing_command(self, tmp_path: Path) -> None:
        result = run_agent(
            ["definitely-not-a-real-command-xyz"],
            working_directory=str(tmp_path),
        )

        assert result.classification is Classification.COMMAND_NOT_FOUND
        assert result.exit_status == 127
        assert "not found" in result.stderr
        assert result.error is not None

    def test_loop_reports_missing_agent_command(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        config = LoopConfig(
            agent_command=["definitely-not-a-real-command-xyz"],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMMAND_NOT_FOUND
        assert "definitely-not-a-real-command-xyz" in (result.adapter_error or "")


class TestMissingVerificationCommand:
    def test_loop_reports_missing_verification_command(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        hook_marker = tmp_path / "hooked.txt"

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=["definitely-not-a-real-command-xyz"],
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.ARCHIVE,
                    command=_write_script(
                        tmp_path,
                        "hook.py",
                        f"""\
                        from pathlib import Path
                        Path({str(hook_marker)!r}).write_text("hooked")
                        """,
                    ),
                    enabled=True,
                ),
            ],
            max_iterations=3,
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMMAND_NOT_FOUND
        assert "definitely-not-a-real-command-xyz" in (result.adapter_error or "")
        assert not hook_marker.exists()


class TestMissingCompletionCommand:
    def test_strategy_raises_completion_check_error(self, tmp_path: Path) -> None:
        strategy = ExternalCommandCompletion(
            check_command=["definitely-not-a-real-command-xyz"],
        )

        try:
            strategy.has_work(str(tmp_path / "task.md"))
        except CompletionCheckError as exc:
            assert "definitely-not-a-real-command-xyz" in str(exc)
        else:
            raise AssertionError("expected CompletionCheckError")

    def test_loop_reports_missing_completion_command(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        hook_marker = tmp_path / "hooked.txt"

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            completion_strategy=ExternalCommandCompletion(
                check_command=["definitely-not-a-real-command-xyz"],
            ),
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.ARCHIVE,
                    command=_write_script(
                        tmp_path,
                        "hook.py",
                        f"""\
                        from pathlib import Path
                        Path({str(hook_marker)!r}).write_text("hooked")
                        """,
                    ),
                    enabled=True,
                ),
            ],
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMMAND_NOT_FOUND
        assert "not found" in (result.adapter_error or "")
        assert not hook_marker.exists()

    def test_missing_workflow_command_is_reported(self, tmp_path: Path) -> None:
        from sisyphusfy.workflows import WorkflowConfig

        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            workflow_config=WorkflowConfig(
                adapter_type="external",
                check_command=["definitely-not-a-real-command-xyz"],
            ),
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMMAND_NOT_FOUND
        assert "not found" in (result.adapter_error or "")
