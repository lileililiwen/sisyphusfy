"""Tests for commit hook index validation and staging safety.

The commit hook MUST refuse to run when pre-existing staged paths are outside
the canonicalized allowlist, MUST apply bounded execution to its `git add`
invocation, and MUST fail when staging cannot complete successfully.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from sisyphusfy.hooks import HookConfig, HookStatus, HookType, run_hook

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
    # `git diff --cached` works only with a valid HEAD; an initial empty commit
    # makes the test repo behave like a real workspace.
    _git(repo, "commit", "--allow-empty", "-m", "init", "--quiet")


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


@NEEDS_GIT
class TestUnrelatedStagedPathRejection:
    def test_unrelated_staged_path_fails_and_does_not_run_commit(
        self, tmp_path: Path
    ) -> None:
        _init_repo(tmp_path)
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed")
        unrelated = tmp_path / "unrelated.txt"
        unrelated.write_text("unrelated")
        # Pre-stage an unrelated path before the hook runs.
        _git(tmp_path, "add", "unrelated.txt")
        assert "unrelated.txt" in _git(
            tmp_path, "diff", "--cached", "--name-only"
        ).stdout

        marker = tmp_path / "commit.marker"
        commit_cmd = _write_script(
            tmp_path,
            "fake_commit.py",
            f"""\
            from pathlib import Path
            Path({str(marker)!r}).write_text("committed")
            """,
        )
        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=commit_cmd,
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )

        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert "unrelated" in (result.error or "")
        assert "index" in (result.error or "").lower() or "staged" in (result.error or "").lower()
        assert not marker.exists(), "commit command must not run when pre-staged path is unrelated"

    def test_only_allowed_paths_pre_staged_passes(
        self, tmp_path: Path
    ) -> None:
        _init_repo(tmp_path)
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed")
        _git(tmp_path, "add", "allowed.txt")

        marker = tmp_path / "commit.marker"
        commit_cmd = _write_script(
            tmp_path,
            "fake_commit.py",
            f"""\
            from pathlib import Path
            Path({str(marker)!r}).write_text("committed")
            """,
        )
        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=commit_cmd,
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )

        result = run_hook(config)
        assert result.status == HookStatus.SUCCESS
        assert marker.exists()

    def test_no_pre_staged_paths_passes(
        self, tmp_path: Path
    ) -> None:
        _init_repo(tmp_path)
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed")

        marker = tmp_path / "commit.marker"
        commit_cmd = _write_script(
            tmp_path,
            "fake_commit.py",
            f"""\
            from pathlib import Path
            Path({str(marker)!r}).write_text("committed")
            """,
        )
        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=commit_cmd,
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )

        result = run_hook(config)
        assert result.status == HookStatus.SUCCESS


@NEEDS_GIT
class TestStagingFailure:
    def test_staging_failure_reported_and_commit_not_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed")

        marker = tmp_path / "commit.marker"
        commit_cmd = _write_script(
            tmp_path,
            "fake_commit.py",
            f"""\
            from pathlib import Path
            Path({str(marker)!r}).write_text("committed")
            """,
        )

        # Simulate a `git add` failure by intercepting subprocess.run only for
        # the staging invocation. Other subprocess calls (such as the pre-staged
        # check) must continue to work.
        import subprocess as _subprocess

        original_run = _subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if isinstance(cmd, list) and cmd[:3] == ["git", "add", "--"]:
                result = _subprocess.CompletedProcess(
                    cmd, 129, stdout="", stderr="fatal: bad path\n"
                )
                return result
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr("sisyphusfy.hooks.subprocess.run", fake_run)

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=commit_cmd,
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )

        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert (
            "stage" in (result.error or "").lower()
            or "fatal" in (result.error or "").lower()
        )
        assert not marker.exists(), "commit command must not run when staging fails"

    def test_staging_timeout_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed")

        marker = tmp_path / "commit.marker"
        commit_cmd = _write_script(
            tmp_path,
            "fake_commit.py",
            f"""\
            from pathlib import Path
            Path({str(marker)!r}).write_text("committed")
            """,
        )

        import subprocess as _subprocess

        original_run = _subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if isinstance(cmd, list) and cmd[:3] == ["git", "add", "--"]:
                raise _subprocess.TimeoutExpired(cmd=cmd, timeout=30.0)
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr("sisyphusfy.hooks.subprocess.run", fake_run)

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=commit_cmd,
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )

        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert "timed out" in (result.error or "").lower()
        assert not marker.exists()
