"""Release metadata, CI, and installers must advertise the same buildable set.

These tests prove the audited gap: release metadata and the CI matrix both
advertised linux/aarch64 while the matrix built it on an x86_64 runner, so the
published tarball contained an x86_64 binary labeled aarch64.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from sisyphusfy.distribution import (
    DEFERRED_TARGETS,
    RELEASE_TARGETS,
    RUNNER_NATIVE_ARCH,
    SUPPORTED_PLATFORMS,
    generate_release_metadata,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
INSTALL_SH = REPO_ROOT / "install.sh"
NPM_LAUNCHER = REPO_ROOT / "npm" / "lib" / "launcher.js"


def _workflow() -> dict:
    return yaml.safe_load(RELEASE_WORKFLOW.read_text())


def _matrix_entries() -> list[dict]:
    return _workflow()["jobs"]["build-artifacts"]["strategy"]["matrix"]["include"]


class TestReleaseTargets:
    def test_targets_have_native_runners(self) -> None:
        for target in RELEASE_TARGETS:
            assert RUNNER_NATIVE_ARCH.get(target.runner) == target.arch, (
                f"{target.platform}-{target.arch} is built on {target.runner}, "
                f"which produces {RUNNER_NATIVE_ARCH.get(target.runner)}"
            )

    def test_deferred_targets_are_absent_from_supported_set(self) -> None:
        supported = {(t.platform, t.arch) for t in RELEASE_TARGETS}
        for target in DEFERRED_TARGETS:
            assert (target.platform, target.arch) not in supported

    def test_deferred_targets_have_no_runner(self) -> None:
        for target in DEFERRED_TARGETS:
            assert target.runner == ""

    def test_supported_platforms_derive_from_targets(self) -> None:
        expected: dict[str, list[str]] = {}
        for target in RELEASE_TARGETS:
            expected.setdefault(target.platform, []).append(target.arch)
        assert SUPPORTED_PLATFORMS == expected


class TestCiMatrix:
    def test_matrix_matches_release_targets(self) -> None:
        matrix = {(e["platform"], e["arch"]) for e in _matrix_entries()}
        assert matrix == {(t.platform, t.arch) for t in RELEASE_TARGETS}

    def test_matrix_runners_are_native(self) -> None:
        for entry in _matrix_entries():
            assert RUNNER_NATIVE_ARCH.get(entry["os"]) == entry["arch"], (
                f"CI builds {entry['platform']}-{entry['arch']} on "
                f"{entry['os']}, which cannot produce that architecture"
            )

    def test_no_deferred_target_in_matrix(self) -> None:
        matrix = {(e["platform"], e["arch"]) for e in _matrix_entries()}
        for target in DEFERRED_TARGETS:
            assert (target.platform, target.arch) not in matrix

    def test_matrix_has_architecture_guard(self) -> None:
        content = RELEASE_WORKFLOW.read_text()
        assert "matrix.arch" in content
        assert "uname -m" in content


class TestMetadataMatchesCi:
    def test_metadata_artifacts_match_matrix(self) -> None:
        metadata = generate_release_metadata("0.1.0")
        artifacts = {(a["platform"], a["arch"]) for a in metadata["artifacts"]}
        matrix = {(e["platform"], e["arch"]) for e in _matrix_entries()}
        assert artifacts == matrix

    def test_metadata_has_no_deferred_artifact(self) -> None:
        metadata = generate_release_metadata("0.1.0")
        for target in DEFERRED_TARGETS:
            assert target.arch not in [
                a["arch"] for a in metadata["artifacts"] if a["platform"] == target.platform
            ]


def _posix_advertised_targets() -> set[str]:
    content = INSTALL_SH.read_text()
    block = re.search(
        r'case "\$\{platform\}-\$\{arch\}" in\n\s*([^\n]*)\)',
        content,
    )
    assert block is not None, "install.sh has no target allowlist"
    return {pair.strip() for pair in block.group(1).split("|") if pair.strip()}


def _npm_advertised_targets() -> set[str]:
    content = NPM_LAUNCHER.read_text()
    block = re.search(r"const SUPPORTED_TARGETS = \[(.*?)\];", content, re.DOTALL)
    assert block is not None, "npm launcher has no target allowlist"
    return set(re.findall(r'"([^"]+)"', block.group(1)))


class TestPyPiPublication:
    def test_workflow_publishes_built_distributions(self) -> None:
        job = _workflow()["jobs"]["publish-pypi"]
        steps = [step.get("uses", "") for step in job["steps"]]
        assert any("pypa/gh-action-pypi-publish" in step for step in steps)
        assert any("python -m build --sdist --wheel" in str(step) for step in job["steps"])

    def test_publication_uses_trusted_publishing(self) -> None:
        job = _workflow()["jobs"]["publish-pypi"]
        assert job["permissions"]["id-token"] == "write"
        assert "PYPI_API_TOKEN" not in RELEASE_WORKFLOW.read_text()

    def test_publication_waits_for_the_github_release(self) -> None:
        job = _workflow()["jobs"]["publish-pypi"]
        assert job["needs"] == "publish-release"


class TestPosixInstallerTargets:
    def test_supported_targets_match_release_metadata(self) -> None:
        assert _posix_advertised_targets() == {
            t.slug for t in RELEASE_TARGETS if t.platform != "win32"
        }

    def test_deferred_target_is_not_advertised(self) -> None:
        advertised = _posix_advertised_targets()
        for target in DEFERRED_TARGETS:
            assert target.slug not in advertised


class TestNpmLauncherTargets:
    def test_supported_targets_match_release_metadata(self) -> None:
        assert _npm_advertised_targets() == {t.slug for t in RELEASE_TARGETS}

    def test_deferred_target_is_not_advertised(self) -> None:
        advertised = _npm_advertised_targets()
        for target in DEFERRED_TARGETS:
            assert target.slug not in advertised

    @pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
    def test_deferred_target_is_rejected_at_runtime(self) -> None:
        for target in DEFERRED_TARGETS:
            platform, arch = target.platform, target.arch
            node_arch = {"x86_64": "x64", "aarch64": "arm64"}[arch]
            result = subprocess.run(
                [
                    "node", "-e",
                    (
                        "const l = require('./lib/launcher.js'); "
                        f"Object.defineProperty(process, 'platform', {{value: '{platform}'}}); "
                        f"Object.defineProperty(process, 'arch', {{value: '{node_arch}'}}); "
                        "try { l.getPlatform(); console.log('accepted'); } "
                        "catch(e) { console.log(e.message); }"
                    ),
                ],
                capture_output=True,
                text=True,
                cwd=NPM_LAUNCHER.parent.parent,
                check=False,
            )
            assert result.returncode == 0
            assert "No prebuilt release" in result.stdout
