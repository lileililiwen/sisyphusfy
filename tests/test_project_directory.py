"""The selected project directory must be used by every subprocess boundary.

These tests prove the audited gap: high-level commands discovered a project but
left the loop working directory at the caller's current directory.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.hooks import HookConfig, HookType
from sisyphusfy.human import cmd_resume, cmd_run
from sisyphusfy.loop import (
    LoopConfig,
    LoopResult,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    run_loop,
)
from sisyphusfy.workflows import WorkflowConfig


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


def _cwd_recorder(target: Path, name: str) -> list[str]:
    return _write_script(
        target,
        name,
        f"""\
        from pathlib import Path
        Path({str(target / (name + ".cwd"))!r}).write_text(str(Path.cwd()))
        """,
    )


class TestLoopUsesWorkingDirectory:
    def test_agent_verification_and_hook_run_in_project(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "task.md").write_text("- [ ] work\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        agent_cmd = _write_script(
            project,
            "agent.py",
            f"""\
            from pathlib import Path
            Path({str(project / 'agent.cwd')!r}).write_text(str(Path.cwd()))
            Path({str(project / 'task.md')!r}).write_text("- [x] done\\n")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(project),
            task_path="task.md",
            prompt_template="do work",
            verification_command=_cwd_recorder(project, "verify.py"),
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.ARCHIVE,
                    command=_cwd_recorder(project, "archive.py"),
                    enabled=True,
                ),
            ],
            max_iterations=2,
        )

        monkeypatch.chdir(elsewhere)
        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMPLETE
        for name in ("agent.cwd", "verify.py.cwd", "archive.py.cwd"):
            recorded = Path((project / name).read_text())
            assert recorded == project.resolve(), f"{name} ran in {recorded}"

    def test_workflow_validation_runs_in_project(self, tmp_path: Path, monkeypatch) -> None:
        project = tmp_path / "project"
        change_dir = project / "openspec" / "changes" / "my-change"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [x] done\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        config = LoopConfig(
            agent_command=_write_script(project, "agent.py", "pass"),
            working_directory=str(project),
            task_path="openspec/changes/my-change/tasks.md",
            prompt_template="do work",
            workflow_config=WorkflowConfig(
                adapter_type="openspec",
                change_dir="openspec/changes/my-change",
                validation_command=_cwd_recorder(project, "validate.py"),
            ),
            max_iterations=2,
        )

        monkeypatch.chdir(elsewhere)
        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMPLETE
        recorded = Path((project / "validate.py.cwd").read_text())
        assert recorded == project.resolve()

    def test_relative_task_path_resolves_against_project(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "task.md").write_text("- [x] done\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "task.md").write_text("- [ ] wrong file\n")

        config = LoopConfig(
            agent_command=_write_script(project, "agent.py", "pass"),
            working_directory=str(project),
            task_path="task.md",
            prompt_template="do work",
            completion_strategy=MarkdownCheckboxCompletion(),
            max_iterations=2,
        )

        monkeypatch.chdir(elsewhere)
        result = run_loop(config)

        assert result.stop_reason == LoopStopReason.COMPLETE
        assert result.final_task_path == str((project / "task.md").resolve())


class TestHighLevelCommandsUseProjectDir:
    def _capture(self, monkeypatch) -> dict:
        captured: dict = {}

        def fake_run_loop(config: LoopConfig) -> LoopResult:
            captured["config"] = config
            return LoopResult(stop_reason=LoopStopReason.COMPLETE, iterations=0)

        monkeypatch.setattr("sisyphusfy.loop.run_loop", fake_run_loop)
        return captured

    def test_run_passes_project_dir_to_loop_and_hooks(self, tmp_path, monkeypatch) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "tasks.md").write_text("- [x] done\n")
        (project / ".sisyphusfy.toml").write_text(
            'adapter = "opencode"\ncommit_allowed_files = ["tasks.md"]\n'
        )
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        captured = self._capture(monkeypatch)
        code = cmd_run(project_dir=str(project), archive=True, commit=True)

        assert code == 0
        config = captured["config"]
        assert config.working_directory == str(project.resolve())
        assert config.completion_hooks
        for hook in config.completion_hooks:
            assert hook.working_directory == str(project.resolve())
        assert {h.hook_type.value for h in config.completion_hooks} == {"archive", "commit"}

    def test_resume_passes_project_dir_to_loop(self, tmp_path, monkeypatch) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / "tasks.md").write_text("- [ ] work\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        captured = self._capture(monkeypatch)
        code = cmd_resume(project_dir=str(project))

        assert code == 0
        assert captured["config"].working_directory == str(project.resolve())

    def test_workflow_config_scoped_to_project(self, tmp_path, monkeypatch) -> None:
        project = tmp_path / "project"
        change_dir = project / "openspec" / "changes" / "my-change"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [x] done\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        captured = self._capture(monkeypatch)
        code = cmd_run(project_dir=str(project), change="my-change")

        assert code == 0
        workflow_config = captured["config"].workflow_config
        assert workflow_config is not None
        assert workflow_config.adapter_type == "openspec"
        assert workflow_config.working_directory == str(project.resolve())
