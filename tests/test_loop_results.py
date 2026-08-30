"""Test JSON loop results and bounded run records."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from sisyphusfy.loop import LoopConfig, LoopStopReason, RunRecord, run_loop


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestLoopResults:
    def test_complete_result_structure(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            task = Path(sys.argv[1])
            task.write_text("- [x] work\\n")
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
        d = result.to_dict()

        assert "stop_reason" in d
        assert "iterations" in d
        assert "run_records" in d
        assert isinstance(d["run_records"], list)

    def test_run_record_fields(self, tmp_path: Path) -> None:
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
            max_iterations=1,
        )

        result = run_loop(config)

        assert len(result.run_records) >= 1
        rec = result.run_records[0]
        assert isinstance(rec, RunRecord)
        assert rec.iteration >= 1
        assert rec.result is not None

    def test_max_records_bound(self, tmp_path: Path) -> None:
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
            max_run_records=2,
        )

        result = run_loop(config)
        assert len(result.run_records) <= 2

    def test_json_serializable(self, tmp_path: Path) -> None:
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
            max_iterations=1,
        )

        result = run_loop(config)
        serialized = json.dumps(result.to_dict(), indent=2)
        parsed = json.loads(serialized)
        assert parsed["stop_reason"] == "unchanged_state"

    def test_stop_reason_values(self, tmp_path: Path) -> None:
        for reason in LoopStopReason:
            assert isinstance(reason.value, str)
