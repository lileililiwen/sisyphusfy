"""Tests for POSIX shell installer."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

INSTALL_SH = Path(__file__).resolve().parent.parent / "install.sh"


class TestPosixInstaller:
    def test_script_exists(self) -> None:
        assert INSTALL_SH.exists()

    def test_script_is_executable(self) -> None:
        assert os.access(INSTALL_SH, os.X_OK)

    def test_help_flag(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "Sisyphusfy" in result.stdout
        assert "--version" in result.stdout
        assert "--dir" in result.stdout
        assert "--dry-run" in result.stdout

    def test_dry_run(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "[dry-run]" in result.stdout
        assert "Would download" in result.stdout
        assert "Would verify checksum" in result.stdout

    def test_dry_run_with_version(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run", "--version", "0.2.0"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "0.2.0" in result.stdout

    def test_dry_run_with_custom_dir(self, tmp_path: Path) -> None:
        install_dir = tmp_path / "custom-install"
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run", "--dir", str(install_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert str(install_dir) in result.stdout

    def test_unknown_flag(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--unknown"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "Unknown option" in result.stderr

    def test_version_override(self) -> None:
        result = subprocess.run(
            ["sh", str(INSTALL_SH), "--dry-run", "--version", "99.99.99"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "99.99.99" in result.stdout
