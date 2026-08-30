"""Test fresh process creation for each iteration."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.loop import LoopConfig, run_loop


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestFreshProcessCreation:
    def test_spawns_new_process_each_iteration(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] step 1\n- [ ] step 2\n")

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
            prompt_template="work on tasks in {task_path}",
            max_iterations=3,
        )

        result = run_loop(config)

        assert result.iterations >= 1
        content = task_path.read_text()
        assert "- [x]" in content

    def test_each_iteration_gets_fresh_state(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

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
            prompt_template="work on tasks in {task_path}",
            max_iterations=3,
        )

        run_loop(config)

        content = task_path.read_text()
        assert "- [ ]" not in content
        assert content.count("- [x]") == 1

    def test_run_agent_called_with_correct_cwd(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cwd_log = tmp_path / "cwd.txt"
        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import os, sys
            from pathlib import Path
            task = Path(sys.argv[1])
            cwd_log = Path("{cwd_log}")
            cwd_log.write_text(os.getcwd())
            task.write_text("- [x] work\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="work on tasks in {task_path}",
            max_iterations=1,
        )

        run_loop(config)

        logged_cwd = cwd_log.read_text().strip()
        assert logged_cwd == str(tmp_path.resolve())
