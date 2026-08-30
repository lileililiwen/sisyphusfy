"""Test Markdown and external-command completion strategies."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.loop import (
    ExternalCommandCompletion,
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


class TestMarkdownCheckboxCompletion:
    def test_all_checked_means_complete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] step 1\n- [x] step 2\n")

        strategy = MarkdownCheckboxCompletion()
        assert strategy.has_work(str(task_path)) is False

    def test_unchecked_means_incomplete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] step 1\n- [ ] step 2\n")

        strategy = MarkdownCheckboxCompletion()
        assert strategy.has_work(str(task_path)) is True

    def test_all_unchecked_means_incomplete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] step 1\n- [ ] step 2\n")

        strategy = MarkdownCheckboxCompletion()
        assert strategy.has_work(str(task_path)) is True

    def test_loop_stops_when_all_checked(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] already done\n")

        cmd = _write_script(
            tmp_path,
            "noop.py",
            """\
            pass
            """,
        )

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=5,
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.iterations == 0


class TestExternalCommandCompletion:
    def test_exit_zero_means_complete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("work")

        cmd = _write_script(
            tmp_path,
            "check.py",
            """\
            pass
            """,
        )

        strategy = ExternalCommandCompletion(check_command=cmd)
        assert strategy.has_work(str(task_path)) is False

    def test_exit_nonzero_means_incomplete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("work")

        cmd = _write_script(
            tmp_path,
            "check.py",
            """\
            import sys
            sys.exit(1)
            """,
        )

        strategy = ExternalCommandCompletion(check_command=cmd)
        assert strategy.has_work(str(task_path)) is True

    def test_loop_stops_on_external_check_success(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("work")

        agent_cmd = _write_script(
            tmp_path,
            "noop.py",
            """\
            pass
            """,
        )

        check_cmd = _write_script(
            tmp_path,
            "check.py",
            """\
            pass
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=5,
            completion_strategy=ExternalCommandCompletion(check_command=check_cmd),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.iterations == 0
