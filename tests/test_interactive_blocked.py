"""Test interactive resolution of blocked agent runs."""

from __future__ import annotations

import io
import sys
import textwrap
from pathlib import Path

from sisyphusfy.loop import LoopConfig, LoopStopReason, PromptAnswer, run_loop


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


# A fake agent that blocks on the first run, then resolves once the prompt
# carries the operator's decision (the augmented prompt contains this phrase).
BLOCK_THEN_RESOLVE = '''\
import sys
prompt = sys.stdin.read()
if "Continue the task with that decision applied." in prompt:
    print("done")
    sys.exit(0)
print("NEED_PERMISSION: delete file", file=sys.stderr)
sys.exit(2)
'''

# A fake agent that always blocks, no matter how often it is re-run.
BLOCK_ALWAYS = '''\
import sys
print("NEED_PERMISSION: delete file", file=sys.stderr)
sys.exit(2)
'''

# A fake agent that always blocks on a custom marker plus context lines.
BLOCK_CUSTOM = '''\
import sys
print("working on the task...")
print("AWAITING_INPUT: pick a region", file=sys.stderr)
sys.exit(2)
'''


class TestDefaultPrompt:
    def test_default_prompt_fires_without_explicit_prompt_user(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """LoopConfig(interactive=True) prompts out of the box (task 1.1)."""
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "agent.py", BLOCK_THEN_RESOLVE)
        monkeypatch.setattr(sys, "stdin", io.StringIO("yes, proceed\n"))

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
        )

        result = run_loop(config)

        assert result.stop_reason != LoopStopReason.BLOCKED
        assert "yes, proceed" in result.run_records[-1].prompt

    def test_custom_marker_extraction(self, tmp_path: Path) -> None:
        """Blocker text uses configured markers, not the fallback dump (task 1.2)."""
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "agent.py", BLOCK_CUSTOM)
        seen: list[str] = []

        def prompt_user(blocker: str) -> PromptAnswer:
            seen.append(blocker)
            return PromptAnswer(denied=True)

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            blocked_markers=["AWAITING_INPUT"],
            prompt_user=prompt_user,
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.BLOCKED
        assert seen == ["AWAITING_INPUT: pick a region"]

    def test_empty_input_denies_visibly(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """Empty input denies and says so instead of silently aborting (task 1.3)."""
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "agent.py", BLOCK_ALWAYS)
        monkeypatch.setattr(sys, "stdin", io.StringIO("\n"))

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
        )

        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.BLOCKED
        assert len(result.run_records) == 1
        assert "denied (empty input)" in capsys.readouterr().err


class TestInteractiveApprove:
    def test_approve_reruns_agent_and_continues(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "agent.py", BLOCK_THEN_RESOLVE)

        calls: list[str] = []

        def prompt_user(blocker: str) -> PromptAnswer:
            calls.append(blocker)
            return PromptAnswer(denied=False, text="yes, proceed")

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            prompt_user=prompt_user,
        )

        result = run_loop(config)

        # The run was resolved, not stopped as blocked.
        assert result.stop_reason != LoopStopReason.BLOCKED
        # Original run plus the interactive re-run.
        assert len(result.run_records) >= 2
        # The re-run prompt carried the operator's decision.
        last_prompt = result.run_records[-1].prompt
        assert "Continue the task with that decision applied." in last_prompt
        assert "yes, proceed" in last_prompt
        assert calls  # the prompt was actually shown

    def test_free_text_answer_folded_into_prompt(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "agent.py", BLOCK_THEN_RESOLVE)

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            prompt_user=lambda _b: PromptAnswer(denied=False, text="use the staging env"),
        )

        result = run_loop(config)
        assert result.stop_reason != LoopStopReason.BLOCKED
        assert "use the staging env" in result.run_records[-1].prompt


class TestInteractiveDeny:
    def test_deny_stops_without_rerun(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "agent.py", BLOCK_ALWAYS)

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            prompt_user=lambda _b: PromptAnswer(denied=True),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.BLOCKED
        # Only the original run; no re-run after denial.
        assert len(result.run_records) == 1
        assert result.blocked_reason is not None
        assert "NEED_PERMISSION" in result.blocked_reason


class TestNonInteractive:
    def test_non_interactive_stops_and_never_prompts(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "agent.py", BLOCK_ALWAYS)

        def prompt_user(blocker: str) -> PromptAnswer:
            raise AssertionError("prompt_user must not be called when non-interactive")

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=False,
            prompt_user=prompt_user,
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.BLOCKED
        assert len(result.run_records) == 1


class TestPromptCap:
    def test_cap_reached_stops_blocked(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(tmp_path, "agent.py", BLOCK_ALWAYS)

        # Always approves but the agent keeps blocking -> must be bounded.
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            max_interactive_prompts=2,
            prompt_user=lambda _b: PromptAnswer(denied=False, text="go"),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.BLOCKED
        # Original + 2 bounded re-runs; never an infinite loop.
        assert len(result.run_records) == 3


class TestVerificationNotRunWhenBlocked:
    def test_verification_skips_on_blocked_stop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        sentinel = tmp_path / "verified"

        agent = _write_script(tmp_path, "agent.py", BLOCK_ALWAYS)
        verify = _write_script(
            tmp_path,
            "verify.py",
            f"import pathlib; pathlib.Path({str(sentinel)!r}).write_text('ran')",
        )

        config = LoopConfig(
            agent_command=agent,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify,
            max_iterations=3,
            interactive=True,
            prompt_user=lambda _b: PromptAnswer(denied=True),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.BLOCKED
        # Verification must not run when the iteration stops blocked.
        assert not sentinel.exists()
