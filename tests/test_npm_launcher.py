"""Tests for npm launcher version/platform selection."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

NPM_DIR = Path(__file__).resolve().parent.parent / "npm"


class TestNpmLauncherPlatform:
    def test_get_platform_linux_x64(self) -> None:
        result = subprocess.run(
            [
                "node", "-e",
                (
                    "const l = require('./lib/launcher.js'); "
                    "Object.defineProperty(process, 'platform', {value: 'linux'}); "
                    "Object.defineProperty(process, 'arch', {value: 'x64'}); "
                    "const p = l.getPlatform(); "
                    "console.log(JSON.stringify(p));"
                ),
            ],
            capture_output=True,
            text=True,
            cwd=NPM_DIR,
            check=False,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["platform"] == "linux"
        assert data["arch"] == "x86_64"

    def test_get_platform_darwin_arm64(self) -> None:
        result = subprocess.run(
            [
                "node", "-e",
                (
                    "const l = require('./lib/launcher.js'); "
                    "Object.defineProperty(process, 'platform', {value: 'darwin'}); "
                    "Object.defineProperty(process, 'arch', {value: 'arm64'}); "
                    "const p = l.getPlatform(); "
                    "console.log(JSON.stringify(p));"
                ),
            ],
            capture_output=True,
            text=True,
            cwd=NPM_DIR,
            check=False,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["platform"] == "darwin"
        assert data["arch"] == "aarch64"

    def test_get_platform_unsupported(self) -> None:
        result = subprocess.run(
            [
                "node", "-e",
                (
                    "const l = require('./lib/launcher.js'); "
                    "Object.defineProperty(process, 'platform', {value: 'freebsd'}); "
                    "try { l.getPlatform(); } catch(e) { console.log(e.message); }"
                ),
            ],
            capture_output=True,
            text=True,
            cwd=NPM_DIR,
            check=False,
        )
        assert result.returncode == 0
        assert "Unsupported platform" in result.stdout


class TestNpmLauncherArtifactNames:
    def test_artifact_name(self) -> None:
        result = subprocess.run(
            [
                "node", "-e",
                (
                    "const l = require('./lib/launcher.js'); "
                    "console.log(l.getArtifactName('0.1.0', 'linux', 'x86_64'));"
                ),
            ],
            capture_output=True,
            text=True,
            cwd=NPM_DIR,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "sisyphusfy-0.1.0-linux-x86_64.tar.gz"

    def test_download_url(self) -> None:
        result = subprocess.run(
            [
                "node", "-e",
                (
                    "const l = require('./lib/launcher.js'); "
                    "console.log(l.getDownloadUrl('0.1.0', 'sisyphusfy-0.1.0-linux-x86_64.tar.gz'));"
                ),
            ],
            capture_output=True,
            text=True,
            cwd=NPM_DIR,
            check=False,
        )
        assert result.returncode == 0
        url = result.stdout.strip()
        assert "github.com" in url
        assert "download/v0.1.0/" in url
        assert "sisyphusfy-0.1.0-linux-x86_64.tar.gz" in url


class TestNpmPackage:
    def test_package_json_exists(self) -> None:
        assert (NPM_DIR / "package.json").exists()

    def test_package_json_has_bin(self) -> None:
        content = json.loads((NPM_DIR / "package.json").read_text())
        assert "bin" in content
        assert "sisyphusfy" in content["bin"]

    def test_launcher_script_exists(self) -> None:
        assert (NPM_DIR / "bin" / "sisyphusfy.js").exists()

    def test_launcher_lib_exists(self) -> None:
        assert (NPM_DIR / "lib" / "launcher.js").exists()
