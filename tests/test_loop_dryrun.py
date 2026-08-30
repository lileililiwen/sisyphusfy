"""Dry-run tests proving agent, verifier, workflow, archive, and commit commands do not execute."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.hooks import HookConfig, HookType
from sisyphusfy.loop import (
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    run_loop,
)


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestLoopDryRunAgent:
    def test_dry_run_agent_creates_no_marker(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        marker = tmp_path / "marker.txt"

        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            Path("{marker}").write_text("created")
            """,
        )

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
            dry_run=True,
        )

        result = run_loop(config)
        assert not marker.exists()
        assert result.stop_reason == LoopStopReason.UNCHANGED_STATE
        assert result.iterations == 1

    def test_dry_run_agent_returns_dry_run_classification(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "noop.py", "print('should not run')")

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
            dry_run=True,
        )

        result = run_loop(config)
        rec = result.run_records[0]
        assert rec.result.classification.value == "dry_run"
        assert rec.result.exit_status is None


class TestLoopDryRunVerification:
    def test_dry_run_verification_not_executed(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        marker = tmp_path / "verify_marker.txt"

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            Path("{marker}").write_text("verified")
            """,
        )
        verify_cmd = _write_script(
            tmp_path,
            "verify.py",
            f"""\
            from pathlib import Path
            Path("{marker}").write_text("should not happen")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify_cmd,
            max_iterations=1,
            dry_run=True,
        )

        result = run_loop(config)
        assert not marker.exists()
        assert result.stop_reason == LoopStopReason.UNCHANGED_STATE


class TestLoopDryRunHooks:
    def test_dry_run_archive_hook_not_executed(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")
        marker = tmp_path / "archive_marker.txt"

        agent_cmd = _write_script(tmp_path, "agent.py", "pass")
        hook_cmd = _write_script(
            tmp_path,
            "hook.py",
            f"""\
            from pathlib import Path
            Path("{marker}").write_text("archived")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="done",
            max_iterations=1,
            dry_run=True,
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.ARCHIVE,
                    command=hook_cmd,
                    enabled=True,
                ),
            ],
        )

        result = run_loop(config)
        assert not marker.exists()
        assert result.completion_pipeline_result is not None
        assert result.completion_pipeline_result.hooks[0].status.value == "dry_run"

    def test_dry_run_commit_hook_not_executed(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")
        marker = tmp_path / "commit_marker.txt"

        agent_cmd = _write_script(tmp_path, "agent.py", "pass")
        hook_cmd = _write_script(
            tmp_path,
            "hook.py",
            f"""\
            from pathlib import Path
            Path("{marker}").write_text("committed")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="done",
            max_iterations=1,
            dry_run=True,
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.COMMIT,
                    command=hook_cmd,
                    allowed_files=["*.py"],
                    enabled=True,
                ),
            ],
        )

        result = run_loop(config)
        assert not marker.exists()
        assert result.completion_pipeline_result is not None
        assert result.completion_pipeline_result.hooks[0].status.value == "dry_run"
