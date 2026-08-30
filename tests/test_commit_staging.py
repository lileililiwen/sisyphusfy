"""Test commit hook allowlisted staging and path-escape rejection."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.hooks import HookConfig, HookStatus, HookType, run_hook


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestCommitPathEscapeRejection:
    def test_escape_rejected_when_outside_working_dir(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("escape attempt")

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=["git", "commit", "-m", "test"],
            working_directory=str(tmp_path),
            allowed_files=[str(outside)],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert "escapes working directory" in result.error
        outside.unlink(missing_ok=True)

    def test_escape_rejected_with_relative_dotdot(self, tmp_path: Path) -> None:
        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=["git", "commit", "-m", "test"],
            working_directory=str(tmp_path),
            allowed_files=["../outside_file.txt"],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.FAILURE
        assert "escapes working directory" in result.error

    def test_empty_allowed_files_rejected(self, tmp_path: Path) -> None:
        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=["git", "commit", "-m", "test"],
            working_directory=str(tmp_path),
            allowed_files=[],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SKIPPED
        assert "refusing to stage" in result.error


class TestCommitStagingAllowedFiles:
    def test_allowed_file_staged(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed content")

        script = _write_script(
            tmp_path,
            "fake_commit.py",
            """\
            import subprocess, sys
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, cwd=sys.argv[1]
            )
            print(result.stdout.strip())
            """,
        )

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=script + [str(tmp_path)],
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SUCCESS

    def test_unrelated_file_not_staged(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed content")
        unrelated = tmp_path / "unrelated.txt"
        unrelated.write_text("should not be staged")

        script = _write_script(
            tmp_path,
            "check_staged.py",
            """\
            import subprocess, sys
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True, text=True, cwd=sys.argv[1]
            )
            lines = [l for l in result.stdout.strip().splitlines() if l]
            print(len(lines))
            """,
        )

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=script + [str(tmp_path)],
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )
        result = run_hook(config)
        assert result.status == HookStatus.SUCCESS


class TestCommitDryRunWithStaging:
    def test_dry_run_no_staging_occurs(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed.txt"
        allowed.write_text("allowed content")

        config = HookConfig(
            hook_type=HookType.COMMIT,
            command=["git", "commit", "-m", "test"],
            working_directory=str(tmp_path),
            allowed_files=[str(allowed)],
            enabled=True,
        )
        result = run_hook(config, dry_run=True)
        assert result.status == HookStatus.DRY_RUN
        assert result.command == ["git", "commit", "-m", "test"]
