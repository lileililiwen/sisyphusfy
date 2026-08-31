"""Verification must run at most once per iteration and before completion hooks.

These tests prove the audited gaps: verification used to run twice in one
iteration, and an initially-complete project could invoke archive/commit hooks
without ever running verification.
"""

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


def _counter_script(tmp: Path, name: str, counter: Path) -> list[str]:
    return _write_script(
        tmp,
        name,
        f"""\
        from pathlib import Path
        counter = Path({str(counter)!r})
        count = int(counter.read_text()) if counter.exists() else 0
        counter.write_text(str(count + 1))
        """,
    )


class TestVerificationRunsOnce:
    def test_once_when_iteration_completes(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        counter = tmp_path / "verify_count.txt"

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            Path({str(task_path)!r}).write_text("- [x] done\\n")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=_counter_script(tmp_path, "verify.py", counter),
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMPLETE
        assert counter.read_text() == "1"

    def test_once_per_incomplete_iteration(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        handoff_path = tmp_path / "HANDOFF.md"
        handoff_path.write_text("start\n")
        counter = tmp_path / "verify_count.txt"

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            handoff = Path({str(handoff_path)!r})
            handoff.write_text(handoff.read_text() + "progress\\n")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            handoff_path=str(handoff_path),
            prompt_template="do work",
            verification_command=_counter_script(tmp_path, "verify.py", counter),
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.MAX_ITERATIONS
        assert result.iterations == 3
        assert counter.read_text() == "3"


class TestVerificationBeforeHooks:
    def test_initially_complete_runs_verification_before_hooks(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")
        verify_marker = tmp_path / "verified.txt"
        hook_marker = tmp_path / "hooked.txt"

        verify_cmd = _write_script(
            tmp_path,
            "verify.py",
            f"""\
            from pathlib import Path
            Path({str(verify_marker)!r}).write_text("verified")
            """,
        )
        hook_cmd = _write_script(
            tmp_path,
            "hook.py",
            f"""\
            from pathlib import Path
            Path({str(hook_marker)!r}).write_text("hooked")
            """,
        )

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify_cmd,
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(hook_type=HookType.ARCHIVE, command=hook_cmd, enabled=True),
            ],
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.iterations == 0
        assert verify_marker.exists()
        assert hook_marker.exists()
        assert result.completion_pipeline_result is not None
        assert result.completion_pipeline_result.hooks[0].status.value == "success"

    def test_failing_verification_skips_hooks_when_initially_complete(
        self, tmp_path: Path
    ) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")
        hook_marker = tmp_path / "hooked.txt"

        verify_cmd = _write_script(tmp_path, "verify.py", "import sys\nsys.exit(1)")
        hook_cmd = _write_script(
            tmp_path,
            "hook.py",
            f"""\
            from pathlib import Path
            Path({str(hook_marker)!r}).write_text("hooked")
            """,
        )

        config = LoopConfig(
            agent_command=_write_script(tmp_path, "agent.py", "pass"),
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify_cmd,
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(hook_type=HookType.ARCHIVE, command=hook_cmd, enabled=True),
            ],
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.VERIFICATION_FAILED
        assert not hook_marker.exists()
        assert result.completion_pipeline_result is None

    def test_failing_verification_skips_hooks_after_iteration(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        hook_marker = tmp_path / "hooked.txt"

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            Path({str(task_path)!r}).write_text("- [x] done\\n")
            """,
        )
        verify_cmd = _write_script(tmp_path, "verify.py", "import sys\nsys.exit(1)")
        hook_cmd = _write_script(
            tmp_path,
            "hook.py",
            f"""\
            from pathlib import Path
            Path({str(hook_marker)!r}).write_text("hooked")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify_cmd,
            max_iterations=3,
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(hook_type=HookType.COMMIT, command=hook_cmd, enabled=True),
            ],
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.VERIFICATION_FAILED
        assert result.iterations == 1
        assert not hook_marker.exists()
        assert result.completion_pipeline_result is None
