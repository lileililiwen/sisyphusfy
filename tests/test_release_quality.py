"""Clean-environment packaging and release metadata checks.

These checks must not depend on a populated dist/ directory, an active
virtual environment, or transient build artifacts.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

from sisyphusfy.distribution import generate_release_metadata

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


class TestReleaseMetadata:
    def test_metadata_is_deterministic(self) -> None:
        first = generate_release_metadata("0.1.0")
        second = generate_release_metadata("0.1.0")
        assert first == second

    def test_metadata_matches_version_argument(self) -> None:
        for version in ("0.1.0", "1.2.3", "99.99.99"):
            metadata = generate_release_metadata(version)
            assert metadata["version"] == version
            for artifact in metadata["artifacts"]:
                assert version in artifact["filename"]
                assert version in artifact["url"]

    def test_metadata_serializes_without_env(self) -> None:
        metadata = generate_release_metadata("0.1.0")
        serialized = json.dumps(metadata)
        assert json.loads(serialized) == metadata


class TestPackagingInputs:
    def test_pyproject_present(self) -> None:
        assert PYPROJECT.exists()

    def test_pyproject_declares_package(self) -> None:
        content = PYPROJECT.read_text()
        assert 'name = "sisyphusfy"' in content
        assert '[tool.setuptools.packages.find]' in content
        assert 'where = ["src"]' in content

    def test_source_package_importable(self) -> None:
        import sisyphusfy

        assert importlib.util.find_spec("sisyphusfy.distribution") is not None
        assert sisyphusfy.__name__ == "sisyphusfy"
