"""Tests for PowerShell installer."""

from __future__ import annotations

from pathlib import Path

INSTALL_PS1 = Path(__file__).resolve().parent.parent / "install.ps1"


class TestPowerShellInstaller:
    def test_script_exists(self) -> None:
        assert INSTALL_PS1.exists()

    def test_script_has_powershell_header(self) -> None:
        content = INSTALL_PS1.read_text()
        assert "#Requires -Version 5.1" in content

    def test_script_has_parameters(self) -> None:
        content = INSTALL_PS1.read_text()
        assert "param(" in content
        assert "$Version" in content
        assert "$InstallDir" in content
        assert "$DryRun" in content

    def test_script_has_functions(self) -> None:
        content = INSTALL_PS1.read_text()
        assert "function Get-Platform" in content
        assert "function Download-File" in content
        assert "function Get-Checksums" in content
        assert "function Verify-Checksum" in content
        assert "function Main" in content

    def test_script_has_usage(self) -> None:
        content = INSTALL_PS1.read_text()
        assert ".SYNOPSIS" in content
        assert ".DESCRIPTION" in content
        assert ".PARAMETER Version" in content
        assert ".PARAMETER InstallDir" in content
        assert ".PARAMETER DryRun" in content

    def test_script_has_dry_run_check(self) -> None:
        content = INSTALL_PS1.read_text()
        assert "if ($DryRun)" in content
        assert "[dry-run]" in content

    def test_script_has_error_handling(self) -> None:
        content = INSTALL_PS1.read_text()
        assert '$ErrorActionPreference = "Stop"' in content

    def test_script_has_security_protocol(self) -> None:
        content = INSTALL_PS1.read_text()
        assert "SecurityProtocol" in content
        assert "Tls12" in content
