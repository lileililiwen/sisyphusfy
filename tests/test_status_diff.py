"""Tests for `sisyphusfy status --diff` and the new `sisyphusfy diff` command.

The human CLI MUST include a repository summary when `--diff` is passed to
`status`, and MUST provide a dedicated `diff` subcommand with `--stat`,
`--staged`, and `--json` flags. A non-Git directory MUST be reported as a
structured unavailable state, not raise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from sisyphusfy.cli import main
from sisyphusfy.human import cmd_diff, cmd_status

GIT_AVAILABLE = shutil.which("git") is not None
NEEDS_GIT = pytest.mark.skipif(not GIT_AVAILABLE, reason="git executable required")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "--quiet", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "commit", "--allow-empty", "-m", "init", "--quiet")


@NEEDS_GIT
class TestStatusWithDiff:
    def test_status_without_diff_still_works(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [x] done\n")
        code = cmd_status(str(tmp_path))
        assert code == 0
        out = capsys.readouterr().out
        assert "adapter:" in out
        assert "main" not in out  # no git info without --diff

    def test_status_with_diff_in_non_repo(self, tmp_path: Path, capsys) -> None:
        (tmp_path / "tasks.md").write_text("- [x] done\n")
        code = cmd_status(str(tmp_path), show_diff=True)
        assert code == 0
        out = capsys.readouterr().out
        assert "not_a_repository" in out or "unavailable" in out

    def test_status_with_diff_in_repo(self, tmp_path: Path, capsys) -> None:
        _init_repo(tmp_path)
        (tmp_path / "tasks.md").write_text("- [x] done\n")
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")

        code = cmd_status(str(tmp_path), show_diff=True)
        assert code == 0
        out = capsys.readouterr().out
        assert "branch:" in out
        assert "main" in out
        assert "changed:" in out

    def test_status_with_diff_json_in_repo(self, tmp_path: Path, capsys) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")

        code = cmd_status(str(tmp_path), show_diff=True, json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert "git" in data
        assert data["git"]["available"] is True
        assert data["git"]["branch"] == "main"
        assert data["git"]["changed_files"] >= 1
        assert "hello.txt" in data["git"]["status_paths"]


@NEEDS_GIT
class TestDiffCommand:
    def test_diff_in_non_repo_is_structured(
        self, tmp_path: Path, capsys
    ) -> None:
        code = cmd_diff(str(tmp_path), json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert data["git"]["available"] is False
        assert data["git"]["reason"] == "not_a_repository"

    def test_diff_default_shows_unstaged(
        self, tmp_path: Path, capsys
    ) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")

        code = cmd_diff(str(tmp_path))
        assert code == 0
        out = capsys.readouterr().out
        assert "hello.txt" in out
        assert "+two" in out

    def test_diff_staged_flag(self, tmp_path: Path, capsys) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")
        _git(tmp_path, "add", "hello.txt")
        file_path.write_text("one\ntwo\nthree\n")

        code = cmd_diff(str(tmp_path), staged=True, json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert data["git"]["available"] is True
        diff_text = data["git"]["diff_text"]
        assert "+two" in diff_text
        assert "three" not in diff_text

    def test_diff_stat_flag(self, tmp_path: Path, capsys) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")

        code = cmd_diff(str(tmp_path), stat=True, json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert "stat_text" in data["git"]
        assert "hello.txt" in data["git"]["stat_text"]
        # Stat mode omits the unified diff body.
        assert data["git"]["diff_text"] == ""

    def test_diff_json_reports_truncation(
        self, tmp_path: Path, capsys
    ) -> None:
        _init_repo(tmp_path)
        big = tmp_path / "big.txt"
        big.write_text("orig\n" * 50)
        _git(tmp_path, "add", "big.txt")
        _git(tmp_path, "commit", "-m", "big", "--quiet")
        big.write_text("line\n" * 4000)

        code = cmd_diff(str(tmp_path), max_bytes=2000, json_output=True)
        assert code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert data["git"]["truncated"] is True


@NEEDS_GIT
class TestDiffCLI:
    def test_cli_diff_in_repo(self, tmp_path: Path, capsys) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")

        with pytest.raises(SystemExit) as exc_info:
            main(["diff", "-d", str(tmp_path)])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "hello.txt" in out

    def test_cli_diff_json_flag(self, tmp_path: Path, capsys) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")

        with pytest.raises(SystemExit) as exc_info:
            main(["diff", "-d", str(tmp_path), "--json"])
        assert exc_info.value.code == 0
        data = json.loads(capsys.readouterr().out.strip())
        assert data["git"]["available"] is True
        assert "+two" in data["git"]["diff_text"]

    def test_cli_status_diff_flag(self, tmp_path: Path, capsys) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")
        (tmp_path / "tasks.md").write_text("- [x] done\n")

        with pytest.raises(SystemExit) as exc_info:
            main(["status", "-d", str(tmp_path), "--diff"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "branch:" in out
        assert "main" in out
