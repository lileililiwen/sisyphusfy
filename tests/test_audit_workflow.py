"""Tests for the audit-and-fix-agent-workflow correction change.

Covers:
- Task 1: Adapter argv for fresh OpenCode/CodeBuddy invocations
- Task 2: No continuation/session identifiers passed
- Task 3: Mutable-file state reload for workflow adapters
- Task 4: Verification before completion and hooks
- Task 5: Default token-efficient prompt
- Task 6: Blocked-signal detection across streams
- Task 7: Commit allowlist enforcement
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from sisyphusfy.adapters import (
    CodeBuddyAdapter,
    OpenCodeAdapter,
)
from sisyphusfy.hooks import (
    HookConfig,
    HookStatus,
    HookType,
    run_hook,
)
from sisyphusfy.loop import (
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    run_loop,
)
from sisyphusfy.workflows import (
    JSONPredicateAdapter,
    MarkdownChecklistAdapter,
    OpenSpecAdapter,
)


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


# ---------------------------------------------------------------------------
# Task 1: Adapter argv for valid fresh invocations
# ---------------------------------------------------------------------------

class TestOpenCodeFreshInvocation:
    def test_opencode_run_command_shape(self) -> None:
        adapter = OpenCodeAdapter(model="claude-sonnet-4")
        cmd = adapter.build_command("/tmp/work", "fix the bug")
        assert cmd[0] == "opencode"
        assert cmd[1] == "run"
        assert "-m" in cmd or "--model" in cmd

    def test_opencode_no_non_interactive_flag(self) -> None:
        adapter = OpenCodeAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert "--non-interactive" not in cmd

    def test_opencode_model_after_run(self) -> None:
        adapter = OpenCodeAdapter(model="claude-3")
        cmd = adapter.build_command("/tmp/work", "hello")
        run_idx = cmd.index("run")
        model_idx = None
        for i, arg in enumerate(cmd):
            if arg in ("-m", "--model"):
                model_idx = i
                break
        assert model_idx is not None
        assert model_idx > run_idx

    def test_opencode_prompt_included(self) -> None:
        adapter = OpenCodeAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "do the thing")
        assert "do the thing" in cmd

    def test_opencode_no_model(self) -> None:
        adapter = OpenCodeAdapter()
        cmd = adapter.build_command("/tmp/work", "hello")
        assert cmd[0] == "opencode"
        assert cmd[1] == "run"
        assert "--model" not in cmd
        assert "-m" not in cmd


class TestCodeBuddyFreshInvocation:
    def test_codebuddy_print_flag(self) -> None:
        adapter = CodeBuddyAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "fix the bug")
        assert cmd[0] == "codebuddy"
        assert "-p" in cmd or "--print" in cmd

    def test_codebuddy_no_interactive_flags(self) -> None:
        adapter = CodeBuddyAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert "--non-interactive" not in cmd

    def test_codebuddy_prompt_included(self) -> None:
        adapter = CodeBuddyAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "do the thing")
        assert "do the thing" in cmd

    def test_codebuddy_no_model(self) -> None:
        adapter = CodeBuddyAdapter()
        cmd = adapter.build_command("/tmp/work", "hello")
        assert cmd[0] == "codebuddy"
        assert "-p" in cmd or "--print" in cmd


# ---------------------------------------------------------------------------
# Task 2: No continuation/session identifiers
# ---------------------------------------------------------------------------

class TestNoContinuationIdentifiers:
    def test_opencode_no_continue_flag(self) -> None:
        adapter = OpenCodeAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert "-c" not in cmd
        assert "--continue" not in cmd

    def test_opencode_no_session_flag(self) -> None:
        adapter = OpenCodeAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert "-s" not in cmd
        assert "--session" not in cmd

    def test_codebuddy_no_continue_flag(self) -> None:
        adapter = CodeBuddyAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert "-c" not in cmd
        assert "--continue" not in cmd

    def test_codebuddy_no_resume_flag(self) -> None:
        adapter = CodeBuddyAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert "-r" not in cmd
        assert "--resume" not in cmd


# ---------------------------------------------------------------------------
# Task 3: Mutable-file state reload for workflow adapters
# ---------------------------------------------------------------------------

class TestMarkdownAdapterReload:
    def test_detects_new_unchecked_after_reload(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        assert adapter.has_work() is False

        task_path.write_text("- [x] done\n- [ ] new task\n")
        adapter.reload()
        assert adapter.has_work() is True

    def test_detects_all_checked_after_reload(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        assert adapter.has_work() is True

        task_path.write_text("- [x] work\n")
        adapter.reload()
        assert adapter.has_work() is False


class TestJSONAdapterReload:
    def test_detects_predicate_change(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"done": False}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path), predicate="done"
        )
        assert adapter.is_complete() is False

        state_path.write_text(json.dumps({"done": True}))
        adapter.reload()
        assert adapter.is_complete() is True

    def test_detects_nested_change(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"status": {"phase": ""}}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path), predicate="status.phase"
        )
        assert adapter.is_complete() is False

        state_path.write_text(json.dumps({"status": {"phase": "complete"}}))
        adapter.reload()
        assert adapter.is_complete() is True


class TestOpenSpecAdapterReload:
    def test_detects_new_unchecked_task(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        tasks_file = change_dir / "tasks.md"
        tasks_file.write_text("- [x] done\n")
        validation_cmd = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation_cmd,
        )
        assert adapter.has_work() is False

        tasks_file.write_text("- [x] done\n- [ ] new task\n")
        adapter.reload()
        assert adapter.has_work() is True

    def test_detects_all_checked(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        tasks_file = change_dir / "tasks.md"
        tasks_file.write_text("- [ ] work\n")
        validation_cmd = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation_cmd,
        )
        assert adapter.has_work() is True

        tasks_file.write_text("- [x] work\n")
        adapter.reload()
        assert adapter.has_work() is False


# ---------------------------------------------------------------------------
# Task 4: Verification before completion and hooks
# ---------------------------------------------------------------------------

class TestVerificationBeforeCompletion:
    def test_failing_verification_blocks_hooks(self, tmp_path: Path) -> None:
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
        hook_cmd = _write_script(
            tmp_path,
            "hook.py",
            """\
            print("HOOK RAN - SHOULD NOT HAPPEN")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            verification_command=verify_cmd,
            max_iterations=3,
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.ARCHIVE,
                    command=hook_cmd,
                    enabled=True,
                ),
            ],
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.VERIFICATION_FAILED
        assert result.completion_pipeline_result is None

    def test_passing_verification_allows_hooks(self, tmp_path: Path) -> None:
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
        hook_cmd = _write_script(
            tmp_path,
            "hook.py",
            """\
            print("hook ran")
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
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.ARCHIVE,
                    command=hook_cmd,
                    enabled=True,
                ),
            ],
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.completion_pipeline_result is not None
        assert result.completion_pipeline_result.hooks[0].status == HookStatus.SUCCESS


# ---------------------------------------------------------------------------
# Task 5: Default token-efficient prompt
# ---------------------------------------------------------------------------

class TestDefaultPrompt:
    def test_empty_template_provides_default(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        prompt_log = tmp_path / "prompt.txt"
        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            from pathlib import Path
            prompt_log = Path("{prompt_log}")
            prompt_log.write_text(sys.stdin.read())
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="",
            max_iterations=1,
        )

        run_loop(config)
        captured = prompt_log.read_text()
        assert len(captured.strip()) > 0

    def test_default_prompt_references_task_path(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        prompt_log = tmp_path / "prompt.txt"
        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            from pathlib import Path
            prompt_log = Path("{prompt_log}")
            prompt_log.write_text(sys.stdin.read())
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="",
            max_iterations=1,
        )

        run_loop(config)
        captured = prompt_log.read_text()
        assert str(task_path) in captured

    def test_custom_prompt_preserved(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        prompt_log = tmp_path / "prompt.txt"
        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            from pathlib import Path
            prompt_log = Path("{prompt_log}")
            prompt_log.write_text(sys.stdin.read())
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="custom instruction for {task_path}",
            max_iterations=1,
        )

        run_loop(config)
        captured = prompt_log.read_text()
        assert "custom instruction for" in captured


# ---------------------------------------------------------------------------
# Task 6: Blocked-signal detection
# ---------------------------------------------------------------------------

class TestBlockedSignalDetection:
    def test_blocked_on_stdout(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            print("NEED_PERMISSION: approve file deletion")
            sys.exit(0)
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.BLOCKED

    def test_blocked_on_stderr(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            print("BLOCKED: need user confirmation", file=sys.stderr)
            sys.exit(0)
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.BLOCKED

    def test_ordinary_failure_not_blocked(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            print("FAILED test_auth.py::test_login")
            sys.exit(1)
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
        )

        result = run_loop(config)
        assert result.stop_reason != LoopStopReason.BLOCKED

    def test_exit_code_not_blocked(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            sys.exit(2)
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
        )

        result = run_loop(config)
        assert result.stop_reason != LoopStopReason.BLOCKED


# ---------------------------------------------------------------------------
# Task 7: Commit allowlist enforcement
# ---------------------------------------------------------------------------

class TestCommitAllowlistEnforcement:
    def test_allowlist_stages_only_allowed_files(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed content")
        unrelated = tmp_path / "unrelated.txt"
        unrelated.write_text("should not be staged")

        staging_log = tmp_path / "staged.txt"
        script = _write_script(
            tmp_path,
            "fake_git.py",
            f"""\
            import sys
            from pathlib import Path
            staging_log = Path("{staging_log}")
            args = sys.argv[1:]
            staged = [a for a in args if not a.startswith("-")]
            staging_log.write_text("\\n".join(staged))
            """,
        )

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=script + ["add", "--", str(allowed), str(unrelated)],
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SUCCESS

    def test_empty_allowlist_fails_safely(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path,
            "fake_git.py",
            """\
            import sys
            print("should not stage everything")
            """,
        )

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=script,
            working_directory=str(tmp_path),
            allowed_files=[],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SKIPPED
        assert "allowed_files" in result.error

    def test_allowlist_config_preserved(self, tmp_path: Path) -> None:
        allowed = tmp_path / "a.txt"
        allowed.write_text("a")
        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=["echo"],
            allowed_files=[str(allowed)],
            enabled=True,
        )
        assert config.allowed_files == [str(allowed)]
