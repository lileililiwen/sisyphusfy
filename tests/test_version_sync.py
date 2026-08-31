"""Release version metadata must have one source of truth.

The Python package, npm manifest, npm launcher, and both installers repeat the
version literal because a shell or JavaScript artifact cannot import Python.
These tests keep those copies in agreement with ``sisyphusfy.__version__``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import sisyphusfy

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
NPM_PACKAGE = REPO_ROOT / "npm" / "package.json"
NPM_LAUNCHER = REPO_ROOT / "npm" / "lib" / "launcher.js"
INSTALL_SH = REPO_ROOT / "install.sh"
INSTALL_PS1 = REPO_ROOT / "install.ps1"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"

VERSION = sisyphusfy.__version__


def _npm_launcher_version() -> str:
    match = re.search(r'^const VERSION = "([^"]+)";', NPM_LAUNCHER.read_text(), re.MULTILINE)
    assert match is not None, "npm launcher has no VERSION constant"
    return match.group(1)


def _install_sh_version() -> str:
    match = re.search(
        r'^VERSION="\$\{SISYPHUSFY_VERSION:-([^}]+)\}"',
        INSTALL_SH.read_text(),
        re.MULTILINE,
    )
    assert match is not None, "install.sh has no default version"
    return match.group(1)


def _install_ps1_version() -> str:
    match = re.search(r'\[string\]\$Version = "([^"]+)"', INSTALL_PS1.read_text())
    assert match is not None, "install.ps1 has no default version"
    return match.group(1)


class TestPackageVersion:
    def test_version_is_semver(self) -> None:
        assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION

    def test_pyproject_has_no_static_version(self) -> None:
        project_block = PYPROJECT.read_text().split("[project]")[1].split("\n[")[0]
        assert re.search(r"^version\s*=", project_block, re.MULTILINE) is None

    def test_pyproject_version_comes_from_package(self) -> None:
        content = PYPROJECT.read_text()
        assert "[tool.setuptools.dynamic]" in content
        assert 'attr = "sisyphusfy.__version__"' in content


class TestInstallerVersions:
    def test_npm_package_version_matches(self) -> None:
        assert json.loads(NPM_PACKAGE.read_text())["version"] == VERSION

    def test_npm_launcher_version_matches(self) -> None:
        assert _npm_launcher_version() == VERSION

    def test_posix_installer_version_matches(self) -> None:
        assert _install_sh_version() == VERSION

    def test_powershell_installer_version_matches(self) -> None:
        assert _install_ps1_version() == VERSION


class TestReleaseWorkflowVerifiesVersion:
    def test_workflow_compares_tag_with_package_version(self) -> None:
        content = RELEASE_WORKFLOW.read_text()
        assert "Verify tag matches package version" in content
        assert "sisyphusfy.__version__" in content
        assert "refusing to publish" in content
