"""Tests for PowerShell installer.

Static fixture checks always run. A live PowerShell syntax check runs only
when a supported PowerShell runtime is available and is reported as an
explicit skip otherwise (never silently passed).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

INSTALL_PS1 = Path(__file__).resolve().parent.parent / "install.ps1"


def _find_powershell() -> str | None:
    """Return a supported PowerShell executable if one actually runs.

    `shutil.which` alone is insufficient: a non-executable wrapper (e.g. a
    broken Snap stub) can appear on PATH while failing at runtime. We probe a
    trivial command so an unusable runtime is reported as unavailable rather
    than producing a false failure.
    """
    for candidate in ("pwsh", "powershell"):
        if not shutil.which(candidate):
            continue
        probe = subprocess.run(
            [candidate, "-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.Major"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if probe.returncode == 0:
            return candidate
    return None


class TestPowerShellInstallerFixtures:
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

    def test_script_references_canonical_repository(self) -> None:
        content = INSTALL_PS1.read_text()
        assert "lileililiwen/sisyphusfy" in content

    def test_script_references_checksum_and_artifact(self) -> None:
        content = INSTALL_PS1.read_text()
        assert "SHA256SUMS.txt" in content
        assert "sisyphusfy-$Version-$platform-$arch.tar.gz" in content
        assert "releases/download/v$Version" in content


class TestPowerShellRuntimeVerification:
    def test_syntax_check_when_available(self) -> None:
        pwsh = _find_powershell()
        if pwsh is None:
            pytest.skip("PowerShell runtime not available or not executable on this host")

        result = subprocess.run(
            [
                pwsh,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    "$errors=$null; "
                    "[System.Management.Automation.Language.Parser]::ParseFile("
                    "'" + str(INSTALL_PS1).replace("'", "''") + "', [ref]$null, [ref]$errors); "
                    "if ($errors.Count -gt 0) { "
                    "Write-Error ($errors | Out-String); exit 1 }"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"PowerShell syntax check failed:\n{result.stdout}\n{result.stderr}"
        )
