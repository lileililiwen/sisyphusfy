"""Tests for workspace progress, blocker detection, path boundaries,
checklist variants, and structured configuration errors.

The new contract moves four failure modes that have bitten real runs:
- The loop stops with UNCHANGED_STATE even when the agent edited source.
- The loop blocks on an ordinary mention of "permission" in agent output.
- A configured task/handoff path can resolve outside the project root.
- An OpenSpec tasks file that uses `- [X]` is not recognised as complete.
- A malformed `.sisyphusfy.toml` silently uses unrelated defaults.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from sisyphusfy.config import (
    ConfigurationError,
    load_config,
)
from sisyphusfy.loop import (
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    _is_blocked,
    run_loop,
)
from sisyphusfy.workflows import (
    OpenSpecAdapter,
    WorkflowError,
)


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestWorkspaceProgressEvidence:
    def test_source_only_change_keeps_loop_running(self, tmp_path: Path) -> None:
        """Agent edits a tracked source file and the loop does not stop on
        the first iteration just because the task/handoff did not change."""
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        handoff_path = tmp_path / "HANDOFF.md"
        handoff_path.write_text("step0\n")
        tracked = tmp_path / "src" / "lib.py"
        tracked.parent.mkdir()
        tracked.write_text("# v1\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            src = Path({str(tracked)!r})
            n = int(src.read_text().split()[-1].lstrip("v"))
            src.write_text(f"# v{{n+1}}\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            handoff_path=str(handoff_path),
            prompt_template="do work",
            max_iterations=4,
            completion_strategy=MarkdownCheckboxCompletion(),
            workspace_evidence=["src/**/*.py"],
        )

        result = run_loop(config)
        # Without workspace evidence, the loop would stop with UNCHANGED_STATE
        # after a single iteration. With it, the source change keeps the loop
        # running until either the task is completed or the agent stops making
        # source changes.
        assert result.iterations >= 2
        assert result.stop_reason is LoopStopReason.MAX_ITERATIONS

    def test_workspace_evidence_disabled_still_unchanged(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        tracked = tmp_path / "src" / "lib.py"
        tracked.parent.mkdir()
        tracked.write_text("# v1\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            Path({str(tracked)!r}).write_text("# v2\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=2,
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.UNCHANGED_STATE

    def test_workspace_change_does_not_complete(self, tmp_path: Path) -> None:
        """Source edits alone must not be treated as completion."""
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] real work\n")
        tracked = tmp_path / "src" / "lib.py"
        tracked.parent.mkdir()
        tracked.write_text("# v1\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            from pathlib import Path
            n = int(Path({str(tracked)!r}).read_text().split()[-1].lstrip("v"))
            Path({str(tracked)!r}).write_text(f"# v{{n+1}}\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=2,
            completion_strategy=MarkdownCheckboxCompletion(),
            workspace_evidence=["src/**/*.py"],
        )

        result = run_loop(config)
        assert result.stop_reason is not LoopStopReason.COMPLETE


class TestBlockerFalsePositives:
    def test_mentions_of_permission_are_not_a_blocker(self, tmp_path: Path) -> None:
        """Ordinary prose about file permissions must not trigger blocked handling."""
        from sisyphusfy.result import Classification, RunResult

        result = RunResult(
            command=["agent"],
            exit_status=0,
            classification=Classification.SUCCESS,
            stdout=(
                "chmod 0644 the config; permission bits control who can read the file\n"
                "tests passed; the file is now executable for the user\n"
            ),
        )
        assert _is_blocked(result) is False

    def test_explicit_blocker_marker_is_a_blocker(self) -> None:
        from sisyphusfy.result import Classification, RunResult

        result = RunResult(
            command=["agent"],
            exit_status=0,
            classification=Classification.SUCCESS,
            stdout="NEED_PERMISSION: cannot reach external service\n",
        )
        assert _is_blocked(result) is True

    def test_explicit_blocked_marker_is_a_blocker(self) -> None:
        from sisyphusfy.result import Classification, RunResult

        result = RunResult(
            command=["agent"],
            exit_status=0,
            classification=Classification.SUCCESS,
            stdout="BLOCKED: waiting on reviewer\n",
        )
        assert _is_blocked(result) is True


class TestPathBoundaries:
    def test_task_path_outside_project_raises(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.md"
        outside.write_text("- [ ] work\n")
        try:
            cmd = _write_script(tmp_path, "noop.py", "pass")
            config = LoopConfig(
                agent_command=cmd,
                working_directory=str(tmp_path),
                task_path=str(outside),
                prompt_template="do work",
            )
            with pytest.raises((ConfigurationError, ValueError, WorkflowError)):
                run_loop(config)
        finally:
            outside.unlink(missing_ok=True)

    def test_relative_path_escape_is_rejected(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.md"
        outside.write_text("- [ ] work\n")
        try:
            cmd = _write_script(tmp_path, "noop.py", "pass")
            config = LoopConfig(
                agent_command=cmd,
                working_directory=str(tmp_path),
                task_path="../outside.md",
                prompt_template="do work",
            )
            with pytest.raises((ConfigurationError, ValueError, WorkflowError)):
                run_loop(config)
        finally:
            outside.unlink(missing_ok=True)


class TestChecklistVariants:
    def test_openspec_uppercase_X_is_complete(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        (change_dir / "tasks.md").write_text("- [X] task 1\n- [X] task 2\n")
        validation = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation,
        )
        assert adapter.is_complete() is True
        assert adapter.has_work() is False

    def test_openspec_lowercase_x_still_works(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        (change_dir / "tasks.md").write_text("- [x] task 1\n- [x] task 2\n")
        validation = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation,
        )
        assert adapter.is_complete() is True


class TestMalformedConfiguration:
    def test_malformed_toml_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".sisyphusfy.toml").write_text("{{{{not valid toml")
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(str(tmp_path))
        assert "sisyphusfy.toml" in str(exc_info.value)

    def test_malformed_toml_via_user_config(self, tmp_path: Path, monkeypatch) -> None:
        user = tmp_path / "config.toml"
        user.write_text("}}}}{{ broken")
        monkeypatch.setattr(
            "sisyphusfy.config._user_config_path", lambda: user
        )
        with pytest.raises(ConfigurationError):
            load_config(str(tmp_path))


class TestMalformedConfigurationInHuman:
    def test_cmd_run_reports_malformed_config(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        from sisyphusfy.human import cmd_run

        (tmp_path / ".sisyphusfy.toml").write_text("{{{{not valid toml")
        (tmp_path / "tasks.md").write_text("- [ ] work\n")
        rc = cmd_run(str(tmp_path))
        captured = capsys.readouterr()
        assert rc != 0
        assert "sisyphusfy.toml" in captured.err or "sisyphusfy.toml" in captured.out

    def test_cmd_run_json_reports_malformed_config(
        self, tmp_path: Path, capsys
    ) -> None:
        from sisyphusfy.human import cmd_run

        (tmp_path / ".sisyphusfy.toml").write_text("{{{{not valid toml")
        (tmp_path / "tasks.md").write_text("- [ ] work\n")
        rc = cmd_run(str(tmp_path), json_output=True)
        data = json.loads(capsys.readouterr().out.strip() or "{}")
        assert rc != 0
        assert "sisyphusfy.toml" in (data.get("error") or "")
