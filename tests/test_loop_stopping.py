"""Test timeout, max-iteration, and blocked stopping."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.loop import LoopConfig, LoopStopReason, run_loop


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestTimeoutStopping:
    def test_agent_timeout_stops_loop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(
            tmp_path,
            "slow.py",
            """\
            import time
            time.sleep(60)
            """,
        )

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            agent_timeout=0.1,
            max_iterations=5,
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.TIMEOUT


class TestMaxIterationStopping:
    def test_max_iterations_stops_loop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] step1\n- [ ] step2\n- [ ] step3\n")

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
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.MAX_ITERATIONS
        assert result.iterations == 3

    def test_single_iteration(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            from pathlib import Path
            task = Path(sys.argv[1])
            task.write_text("unchanged\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.MAX_ITERATIONS
        assert result.iterations == 1


class TestBlockedStopping:
    def test_agent_blocked_stops_loop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(
            tmp_path,
            "blocked.py",
            """\
            import sys
            print("NEED_PERMISSION: delete file", file=sys.stderr)
            sys.exit(2)
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
        assert result.stop_reason == LoopStopReason.BLOCKED
        assert result.iterations == 1

    def test_agent_failure_not_blocked(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(
            tmp_path,
            "fail.py",
            """\
            import sys
            sys.exit(1)
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
        assert result.iterations == 1
