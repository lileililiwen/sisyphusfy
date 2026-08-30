"""Test verification success and failure classification."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

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


class TestVerification:
    def test_verification_success_marks_complete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            task = Path(sys.argv[1])
            task.write_text("- [x] done\\n")
            """,
        )

        verify_cmd = _write_script(
            tmp_path,
            "verify.py",
            """\
            pass
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify_cmd,
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.iterations == 1

    def test_verification_failure_stops_loop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            task = Path(sys.argv[1])
            task.write_text("- [x] done\\n")
            """,
        )

        verify_cmd = _write_script(
            tmp_path,
            "verify.py",
            """\
            import sys
            sys.exit(1)
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify_cmd,
            max_iterations=3,
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.VERIFICATION_FAILED
        assert result.iterations == 1

    def test_no_verification_skips_check(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            task = Path(sys.argv[1])
            task.write_text("- [x] done\\n")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE

    def test_verification_timeout_stops_loop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            task = Path(sys.argv[1])
            task.write_text("- [x] done\\n")
            """,
        )

        verify_cmd = _write_script(
            tmp_path,
            "verify.py",
            """\
            import time
            time.sleep(60)
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify_cmd,
            verification_timeout=0.1,
            max_iterations=3,
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.TIMEOUT
