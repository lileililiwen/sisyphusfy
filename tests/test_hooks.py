"""Test optional completion hooks."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.hooks import (
    HookConfig,
    HookStatus,
    HookType,
    run_completion_pipeline,
    run_hook,
)
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


class TestDisabledHooks:
    def test_disabled_hook_skips(self, tmp_path: Path) -> None:
        config = HookConfig(
            hook_type=HookType.ARCHIVE,
            command=["echo", "should not run"],
            enabled=False,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SKIPPED
        assert result.error == "hook disabled"

    def test_disabled_hooks_in_loop(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            pass
            """,
        )

        loop_config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="done",
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.ARCHIVE,
                    command=["echo", "archive"],
                    enabled=False,
                ),
            ],
        )

        result = run_loop(loop_config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.completion_pipeline_result is not None
        assert result.completion_pipeline_result.hooks[0].status == HookStatus.SKIPPED


class TestDryRunHooks:
    def test_dry_run_returns_dry_run_status(self, tmp_path: Path) -> None:
        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=["git", "commit", "-m", "test"],
            allowed_files=["*.py"],
            enabled=True,
        )
        result = run_hook(config, dry_run=True)
        assert result.status == HookStatus.DRY_RUN
        assert result.command == ["git", "commit", "-m", "test"]

    def test_dry_run_no_workspace_mutation(self, tmp_path: Path) -> None:
        file_path = tmp_path / "test.txt"
        file_path.write_text("original")

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=["rm", str(file_path)],
            working_directory=str(tmp_path),
            allowed_files=["*.txt"],
            enabled=True,
        )
        result = run_hook(config, dry_run=True)
        assert result.status == HookStatus.DRY_RUN
        assert file_path.exists()


class TestExplicitFileAllowlist:
    def test_allowlist_in_config(self, tmp_path: Path) -> None:
        from tests.test_commit_staging import _init_repo

        _init_repo(tmp_path)
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed")

        script = _write_script(
            tmp_path,
            "fake_git.py",
            """\
            print("committed")
            """,
        )

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=script,
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SUCCESS
        assert config.allowed_files == [str(allowed)]


class TestArchiveHook:
    def test_archive_success(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path,
            "fake_openspec.py",
            """\
            print("archived")
            """,
        )

        config = HookConfig(
            hook_type=HookType.ARCHIVE,
            command=script,
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SUCCESS
        assert "archived" in result.stdout

    def test_archive_failure(self, tmp_path: Path) -> None:
        script = _write_script(
            tmp_path,
            "fail_openspec.py",
            """\
            import sys
            print("error", file=sys.stderr)
            sys.exit(1)
            """,
        )

        config = HookConfig(
            hook_type=HookType.ARCHIVE,
            command=script,
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert result.error == "exit code 1"


class TestCommitHook:
    def test_commit_success(self, tmp_path: Path) -> None:
        from tests.test_commit_staging import _init_repo

        _init_repo(tmp_path)
        allowed = tmp_path / "allowed.py"
        allowed.write_text("x = 1\n")
        script = _write_script(
            tmp_path,
            "fake_git.py",
            """\
            print("committed")
            """,
        )

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=script,
            allowed_files=[str(allowed)],
            working_directory=str(tmp_path),
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SUCCESS
        assert "committed" in result.stdout

    def test_commit_failure_stops_pipeline(self, tmp_path: Path) -> None:
        fail_script = _write_script(
            tmp_path,
            "fail.py",
            """\
            import sys
            sys.exit(1)
            """,
        )
        success_script = _write_script(
            tmp_path,
            "success.py",
            """\
            print("should not run")
            """,
        )

        hooks = [
            HookConfig(
                hook_type=HookType.COMMIT,
                command=fail_script,
                allowed_files=["*.py"],
                enabled=True,
            ),
            HookConfig(
                hook_type=HookType.ARCHIVE,
                command=success_script,
                enabled=True,
            ),
        ]

        result = run_completion_pipeline(hooks)
        assert result.stopped_early is True
        assert len(result.hooks) == 1
        assert result.hooks[0].status == HookStatus.FAILURE


class TestCompletionPipeline:
    def test_all_hooks_run(self, tmp_path: Path) -> None:
        from tests.test_commit_staging import _init_repo

        _init_repo(tmp_path)
        allowed = tmp_path / "allowed.py"
        allowed.write_text("x = 1\n")
        script1 = _write_script(
            tmp_path,
            "hook1.py",
            """\
            print("hook1")
            """,
        )
        script2 = _write_script(
            tmp_path,
            "hook2.py",
            """\
            print("hook2")
            """,
        )

        hooks = [
            HookConfig(
                hook_type=HookType.ARCHIVE,
                command=script1,
                working_directory=str(tmp_path),
                enabled=True,
            ),
            HookConfig(
                hook_type=HookType.COMMIT,
                command=script2,
                working_directory=str(tmp_path),
                allowed_files=[str(allowed)],
                enabled=True,
            ),
        ]

        result = run_completion_pipeline(hooks)
        assert result.stopped_early is False
        assert len(result.hooks) == 2
        assert all(h.status == HookStatus.SUCCESS for h in result.hooks)

    def test_no_command_skips(self, tmp_path: Path) -> None:
        config = HookConfig(
            hook_type=HookType.ARCHIVE,
            command=[],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SKIPPED
        assert result.error == "no command configured"


class TestHookWithLoop:
    def test_hooks_run_on_complete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")

        agent_cmd = _write_script(
            tmp_path,
            "agent.py",
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
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="done",
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
        assert len(result.completion_pipeline_result.hooks) == 1
        assert result.completion_pipeline_result.hooks[0].status == HookStatus.SUCCESS
