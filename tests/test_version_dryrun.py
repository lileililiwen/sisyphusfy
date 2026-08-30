"""Tests for version override and dry-run behavior."""

from __future__ import annotations

import subprocess
from pathlib import Path

INSTALL_SH = Path(__file__).resolve().parent.parent / "install.sh"


class TestVersionOverride:
    def test_default_version_in_output(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_custom_version_in_output(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run", "--version", "2.0.0"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "2.0.0" in result.stdout
        assert "0.1.0" not in result.stdout

    def test_version_in_download_url(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run", "--version", "1.5.0"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "v1.5.0" in result.stdout


class TestDryRunBehavior:
    def test_dry_run_no_network(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "curl" not in result.stdout.lower() or "[dry-run]" in result.stdout
        assert "wget" not in result.stdout.lower() or "[dry-run]" in result.stdout

    def test_dry_run_shows_all_steps(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "Would download" in result.stdout
        assert "Would verify checksum" in result.stdout
        assert "Would extract" in result.stdout
        assert "Would print PATH instructions" in result.stdout

    def test_dry_run_with_all_options(self, tmp_path: Path) -> None:
        install_dir = tmp_path / "test-install"
        result = subprocess.run(
            [
                "sh", str(INSTALL_SH), "--dry-run",
                "--version", "3.0.0",
                "--dir", str(install_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "3.0.0" in result.stdout
        assert str(install_dir) in result.stdout
