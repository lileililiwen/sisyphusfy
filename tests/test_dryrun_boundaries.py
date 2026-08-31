"""Dry-run must not execute external completion or workflow validation commands.

These tests prove the audited gap: a low-level loop with an external completion
check used to execute that check even with ``--dry-run``.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.loop import (
    ExternalCommandCompletion,
    LoopConfig,
    LoopStopReason,
    run_loop,
)
from sisyphusfy.workflows import (
    ExternalCommandAdapter,
    OpenSpecAdapter,
    WorkflowConfig,
)


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


def _marker_writer(marker: Path) -> str:
    return f"""\
    from pathlib import Path
    Path({str(marker)!r}).write_text("executed")
    """


class TestExternalCompletionInDryRun:
    def test_check_command_does_not_execute(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        marker = tmp_path / "check_executed.txt"

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=2,
            dry_run=True,
            completion_strategy=ExternalCommandCompletion(
                check_command=_write_script(tmp_path, "check.py", _marker_writer(marker)),
            ),
        )

        result = run_loop(config)

        assert not marker.exists()
        assert result.stop_reason == LoopStopReason.DRY_RUN

    def test_check_command_runs_when_dry_run_disabled(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        marker = tmp_path / "check_executed.txt"

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
            dry_run=False,
            completion_strategy=ExternalCommandCompletion(
                check_command=_write_script(tmp_path, "check.py", _marker_writer(marker)),
            ),
        )

        run_loop(config)

        assert marker.exists()

    def test_strategy_itself_suppresses_execution(self, tmp_path: Path) -> None:
        marker = tmp_path / "check_executed.txt"
        strategy = ExternalCommandCompletion(
            check_command=_write_script(tmp_path, "check.py", _marker_writer(marker)),
            dry_run=True,
        )

        assert strategy.has_work(str(tmp_path / "task.md")) is True
        assert not marker.exists()


class TestWorkflowAdaptersInDryRun:
    def test_external_workflow_check_does_not_execute(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        marker = tmp_path / "workflow_check_executed.txt"

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=2,
            dry_run=True,
            workflow_config=WorkflowConfig(
                adapter_type="external",
                check_command=_write_script(tmp_path, "wf_check.py", _marker_writer(marker)),
            ),
        )

        result = run_loop(config)

        assert not marker.exists()
        assert result.stop_reason == LoopStopReason.DRY_RUN

    def test_openspec_validation_does_not_execute(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "openspec" / "changes" / "my-change"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [x] done\n")
        marker = tmp_path / "validation_executed.txt"

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(change_dir / "tasks.md"),
            prompt_template="do work",
            max_iterations=2,
            dry_run=True,
            workflow_config=WorkflowConfig(
                adapter_type="openspec",
                change_dir=str(change_dir),
                validation_command=_write_script(
                    tmp_path, "validate.py", _marker_writer(marker)
                ),
            ),
        )

        result = run_loop(config)

        assert not marker.exists()
        assert result.stop_reason == LoopStopReason.DRY_RUN

    def test_openspec_adapter_skips_validation_when_dry_run(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        (change_dir / "tasks.md").write_text("- [x] done\n")
        marker = tmp_path / "validation_executed.txt"

        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=_write_script(tmp_path, "validate.py", _marker_writer(marker)),
            dry_run=True,
        )

        assert adapter.is_complete() is True
        assert not marker.exists()

        OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=_write_script(tmp_path, "validate.py", _marker_writer(marker)),
        ).is_complete()

        assert marker.exists()

    def test_external_adapter_skips_check_when_dry_run(self, tmp_path: Path) -> None:
        marker = tmp_path / "workflow_check_executed.txt"

        adapter = ExternalCommandAdapter(
            check_command=_write_script(tmp_path, "wf_check.py", _marker_writer(marker)),
            dry_run=True,
        )

        assert adapter.is_complete() is False
        assert not marker.exists()
