"""Tests for human-friendly CLI commands."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from sisyphusfy.cli import main
from sisyphusfy.human import cmd_doctor, cmd_init, cmd_resume, cmd_run, cmd_status


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [str(path)]


class TestInitCommand:
    def test_init_creates_config(self, tmp_path: Path, capsys) -> None:
        code = cmd_init(str(tmp_path))
        assert code == 0
        config_file = tmp_path / ".sisyphusfy.toml"
        assert config_file.exists()

    def test_init_json_output(self, tmp_path: Path, capsys) -> None:
        code = cmd_init(str(tmp_path), json_output=True)
        assert code == 0
        out = capsys.readouterr().out.strip()
        data = json.loads(out)
        assert data["created"] is True

    def test_init_fails_without_force(self, tmp_path: Path, capsys) -> None:
        (tmp_path / ".sisyphusfy.toml").write_text("existing")
        code = cmd_init(str(tmp_path))
        assert code == 1
        err = capsys.readouterr().err
        assert "already exists" in err

    def test_init_force_overwrites(self, tmp_path: Path) -> None:
        (tmp_path / ".sisyphusfy.toml").write_text("old")
        code = cmd_init(str(tmp_path), force=True)
        assert code == 0
        content = (tmp_path / ".sisyphusfy.toml").read_text()
        assert "opencode" in content

    def test_init_cli_subcommand(self, tmp_path: Path, capsys) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["init", "-d", str(tmp_path)])
        assert exc_info.value.code == 0
        assert (tmp_path / ".sisyphusfy.toml").exists()


class TestRunCommand:
    def test_run_no_tasks_fails(self, tmp_path: Path, capsys) -> None:
        code = cmd_run(str(tmp_path))
        assert code == 1
        err = capsys.readouterr().err
        assert "no task file found" in err

    def test_run_with_task_dry_run(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task 1\n")
        code = cmd_run(str(tmp_path), dry_run=True)
        assert code == 0
        out = capsys.readouterr().out
        assert "dry-run" in out

    def test_run_json_dry_run(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task 1\n")
        code = cmd_run(str(tmp_path), dry_run=True, json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert data["dry_run"] is True

    def test_run_openspec_change(self, tmp_path: Path, capsys) -> None:
        change_dir = tmp_path / "openspec" / "changes" / "my-change"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [ ] implement feature\n")
        code = cmd_run(str(tmp_path), change="my-change", dry_run=True)
        assert code == 0
        out = capsys.readouterr().out
        assert "openspec" in out.lower() or "my-change" in out

    def test_run_unknown_change_fails(self, tmp_path: Path, capsys) -> None:
        code = cmd_run(str(tmp_path), change="nonexistent")
        assert code == 1
        err = capsys.readouterr().err
        assert "change not found" in err

    def test_run_archive_flag(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [x] done\n")
        code = cmd_run(str(tmp_path), dry_run=True, archive=True)
        assert code == 0
        out = capsys.readouterr().out
        assert "archive" in out.lower()

    def test_run_commit_flag(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [x] done\n")
        code = cmd_run(str(tmp_path), dry_run=True, commit=True)
        assert code == 0
        out = capsys.readouterr().out
        assert "commit" in out.lower()

    def test_run_cli_subcommand(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task 1\n")
        with pytest.raises(SystemExit) as exc_info:
            main(["run", "-d", str(tmp_path), "--dry-run"])
        assert exc_info.value.code == 0


class TestResumeCommand:
    def test_resume_no_tasks_fails(self, tmp_path: Path, capsys) -> None:
        code = cmd_resume(str(tmp_path))
        assert code == 1
        err = capsys.readouterr().err
        assert "no task file found" in err

    def test_resume_with_task_dry_run(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task 1\n")
        code = cmd_resume(str(tmp_path), dry_run=True)
        assert code == 0
        out = capsys.readouterr().out
        assert "dry-run" in out

    def test_resume_json_output(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task 1\n")
        code = cmd_resume(str(tmp_path), dry_run=True, json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert data["dry_run"] is True

    def test_resume_cli_subcommand(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task 1\n")
        with pytest.raises(SystemExit) as exc_info:
            main(["resume", "-d", str(tmp_path), "--dry-run"])
        assert exc_info.value.code == 0


class TestStatusCommand:
    def test_status_empty_project(self, tmp_path: Path, capsys) -> None:
        code = cmd_status(str(tmp_path))
        assert code == 0
        out = capsys.readouterr().out
        assert "adapter:" in out
        assert "(no task file)" in out

    def test_status_with_tasks(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [x] done\n- [ ] todo\n")
        code = cmd_status(str(tmp_path))
        assert code == 0
        out = capsys.readouterr().out
        assert "1 checked" in out
        assert "1 unchecked" in out
        assert "in_progress" in out

    def test_status_complete_tasks(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [x] done\n- [x] also done\n")
        code = cmd_status(str(tmp_path))
        assert code == 0
        out = capsys.readouterr().out
        assert "complete" in out

    def test_status_json_output(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task 1\n")
        code = cmd_status(str(tmp_path), json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert "tasks_checked" in data
        assert "tasks_unchecked" in data
        assert "state" in data

    def test_status_with_handoff(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task\n")
        (tmp_path / "HANDOFF.md").write_text("handoff\n")
        code = cmd_status(str(tmp_path))
        assert code == 0
        out = capsys.readouterr().out
        assert "HANDOFF.md" in out

    def test_status_openspec_change(self, tmp_path: Path, capsys) -> None:
        change_dir = tmp_path / "openspec" / "changes" / "active"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [ ] task\n")
        code = cmd_status(str(tmp_path))
        assert code == 0
        out = capsys.readouterr().out
        assert "active" in out

    def test_status_cli_subcommand(self, tmp_path: Path, capsys) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["status", "-d", str(tmp_path)])
        assert exc_info.value.code == 0


class TestDoctorCommand:
    def test_doctor_empty_project(self, tmp_path: Path, capsys) -> None:
        cmd_doctor(str(tmp_path))
        out = capsys.readouterr().out
        assert "status:" in out

    def test_doctor_missing_adapter(self, tmp_path: Path, capsys) -> None:
        (tmp_path / ".sisyphusfy.toml").write_text('adapter = "nonexistent"\n')
        code = cmd_doctor(str(tmp_path))
        assert code == 1
        out = capsys.readouterr().out
        assert "issues" in out

    def test_doctor_json_output(self, tmp_path: Path, capsys) -> None:
        code = cmd_doctor(str(tmp_path), json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert "issues" in data
        assert "warnings" in data
        assert "ok" in data

    def test_doctor_warns_no_tasks(self, tmp_path: Path, capsys) -> None:
        cmd_doctor(str(tmp_path))
        out = capsys.readouterr().out
        assert "no task file found" in out

    def test_doctor_warns_no_config(self, tmp_path: Path, capsys) -> None:
        cmd_doctor(str(tmp_path))
        out = capsys.readouterr().out
        assert ".sisyphusfy.toml" in out

    def test_doctor_cli_subcommand(self, tmp_path: Path, capsys) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["doctor", "-d", str(tmp_path)])
        assert exc_info.value.code == 0


class TestBackwardCompatibility:
    def test_loop_subcommand_still_works(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n")

        cmd = _write_script(tmp_path, "noop.py", "pass")

        argv = [
            "loop",
            "--task-path", str(task_path),
            "--working-directory", str(tmp_path),
            "--completion-strategy", "markdown",
            "--max-iterations", "1",
            "--",
        ] + cmd

        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        assert exc_info.value.code == 0

    def test_single_command_still_works(self, tmp_path: Path, capsys) -> None:
        cmd = _write_script(tmp_path, "ok.py", "print('hello')")
        try:
            main(["--dry-run", "--", "python3"] + cmd)
        except SystemExit:
            pass
        out = capsys.readouterr().out
        assert "dry-run" in out
