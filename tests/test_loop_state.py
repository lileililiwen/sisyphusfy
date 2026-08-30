"""Test task/handoff snapshots and unchanged-state stopping."""

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


class TestStateSnapshots:
    def test_unchanged_state_stops_loop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

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
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.UNCHANGED_STATE
        assert result.iterations >= 1

    def test_changed_state_continues_loop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] step1\n- [ ] step2\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            task = Path(sys.argv[1])
            lines = task.read_text().splitlines()
            for i, line in enumerate(lines):
                if line.startswith("- [ ]"):
                    lines[i] = line.replace("- [ ]", "- [x]", 1)
                    break
            task.write_text("\\n".join(lines) + "\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.iterations == 2

    def test_handoff_change_detected(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        handoff_path = tmp_path / "HANDOFF.md"
        handoff_path.write_text("step0\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            task = Path(sys.argv[1])
            handoff = Path(sys.argv[2])
            h = handoff.read_text().strip()
            n = int(h.replace("step", ""))
            handoff.write_text(f"step{n+1}\\n")
            task.write_text("- [x] work\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd + [str(task_path), str(handoff_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            handoff_path=str(handoff_path),
            prompt_template="do work",
            max_iterations=3,
        )

        result = run_loop(config)
        assert result.stop_reason != LoopStopReason.UNCHANGED_STATE

    def test_unchanged_task_changed_handoff_continues(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        handoff_path = tmp_path / "HANDOFF.md"
        handoff_path.write_text("step0\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            task = Path(sys.argv[1])
            handoff = Path(sys.argv[2])
            h = handoff.read_text().strip()
            n = int(h.replace("step", ""))
            handoff.write_text(f"step{n+1}\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd + [str(task_path), str(handoff_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            handoff_path=str(handoff_path),
            prompt_template="do work",
            max_iterations=3,
        )

        result = run_loop(config)
        assert result.stop_reason != LoopStopReason.UNCHANGED_STATE
