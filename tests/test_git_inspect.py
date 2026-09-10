"""Tests for the read-only Git inspection adapter.

The adapter MUST report repository availability without raising, return a
bounded unified diff with a truncation flag, and surface staged/unstaged
selections based on the requested mode. Missing Git or a non-repository
directory is a structured unavailable state.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sisyphusfy.git import (
    DiffMode,
    inspect,
)

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
class TestAvailability:
    def test_unavailable_for_non_repo(self, tmp_path: Path) -> None:
        snapshot = inspect(tmp_path)
        assert snapshot.available is False
        assert snapshot.reason == "not_a_repository"
        assert snapshot.status_entries == []
        assert snapshot.diff_text == ""
        assert snapshot.truncated is False
        assert snapshot.changed_files == 0
        assert snapshot.branch == ""

    def test_available_for_repo(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        snapshot = inspect(tmp_path)
        assert snapshot.available is True
        assert snapshot.reason == ""
        assert snapshot.branch == "main"

    def test_no_raises_when_git_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Even when `git` is missing on PATH, the adapter must report a
        # structured unavailable result.
        monkeypatch.setattr("sisyphusfy.git._GIT_COMMAND", ["definitely-not-a-real-git-xyz"])
        monkeypatch.setattr("shutil.which", lambda _: None)
        snapshot = inspect(tmp_path)
        assert snapshot.available is False
        assert snapshot.reason == "git_unavailable"


@NEEDS_GIT
class TestStatus:
    def test_status_includes_modified_files(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        modified = tmp_path / "modified.txt"
        modified.write_text("hello")
        _git(tmp_path, "add", "modified.txt")
        _git(tmp_path, "commit", "-m", "add", "--quiet")
        modified.write_text("hello world")

        snapshot = inspect(tmp_path)
        assert snapshot.available is True
        statuses = [entry.status for entry in snapshot.status_entries]
        assert "modified.txt" in snapshot.status_paths
        assert any(s.startswith((" M", "M ")) for s in statuses)
        assert snapshot.changed_files >= 1

    def test_status_includes_staged_files(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        staged = tmp_path / "staged.txt"
        staged.write_text("hello")
        _git(tmp_path, "add", "staged.txt")

        snapshot = inspect(tmp_path)
        assert snapshot.available is True
        assert "staged.txt" in snapshot.status_paths
        statuses = [entry.status for entry in snapshot.status_entries]
        assert any(s.startswith(("A ", "A.")) for s in statuses)


@NEEDS_GIT
class TestDiff:
    def test_unified_diff_for_unstaged_changes(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")

        snapshot = inspect(tmp_path, mode=DiffMode.UNSTAGED)
        assert snapshot.available is True
        assert "hello.txt" in snapshot.diff_text
        assert "+two" in snapshot.diff_text

    def test_staged_diff_uses_cached(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "hello.txt"
        file_path.write_text("one\n")
        _git(tmp_path, "add", "hello.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("one\ntwo\n")
        _git(tmp_path, "add", "hello.txt")
        file_path.write_text("one\ntwo\nthree\n")  # unstaged change on top

        snapshot = inspect(tmp_path, mode=DiffMode.STAGED)
        assert snapshot.available is True
        # The staged content is "one\ntwo" -- the cached diff must NOT
        # contain the further "three" addition that lives only in the
        # working tree.
        assert "hello.txt" in snapshot.diff_text
        assert "+two" in snapshot.diff_text
        assert "three" not in snapshot.diff_text

    def test_truncation_flag_when_diff_exceeds_limit(
        self, tmp_path: Path
    ) -> None:
        _init_repo(tmp_path)
        big = tmp_path / "big.txt"
        # A 4000-line file (~32KB) replaces the prior content with completely
        # different lines so the unified diff is roughly the size of the new
        # file and easily exceeds a 2KB truncation budget.
        original = "\n".join(f"orig {i}" for i in range(50)) + "\n"
        big.write_text(original)
        _git(tmp_path, "add", "big.txt")
        _git(tmp_path, "commit", "-m", "big", "--quiet")
        new_lines = "\n".join(f"line {i}" for i in range(4000)) + "\n"
        big.write_text(new_lines)

        snapshot = inspect(tmp_path, mode=DiffMode.UNSTAGED, max_bytes=2000)
        assert snapshot.available is True
        assert snapshot.truncated is True
        assert len(snapshot.diff_text.encode("utf-8")) <= 2000 + 64

    def test_no_truncation_when_within_limit(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        file_path = tmp_path / "small.txt"
        file_path.write_text("a\n")
        _git(tmp_path, "add", "small.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        file_path.write_text("a\nb\n")

        snapshot = inspect(tmp_path, mode=DiffMode.UNSTAGED, max_bytes=8000)
        assert snapshot.available is True
        assert snapshot.truncated is False

    def test_diff_text_empty_when_no_changes(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        snapshot = inspect(tmp_path, mode=DiffMode.UNSTAGED)
        assert snapshot.available is True
        assert snapshot.diff_text == ""
        assert snapshot.truncated is False


@NEEDS_GIT
class TestStat:
    def test_stat_returns_per_file_summary(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("first\n")
        b.write_text("first\n")
        _git(tmp_path, "add", "a.txt", "b.txt")
        _git(tmp_path, "commit", "-m", "init", "--quiet")
        a.write_text("first\nsecond\n")
        b.write_text("first\nsecond\n")

        snapshot = inspect(tmp_path, mode=DiffMode.UNSTAGED, stat_only=True)
        assert snapshot.available is True
        # Two files changed; each with 1 insertion.
        assert "a.txt" in snapshot.stat_text
        assert "b.txt" in snapshot.stat_text
        assert "2 files changed" in snapshot.stat_text
        # Stat mode returns no unified diff body.
        assert snapshot.diff_text == ""
