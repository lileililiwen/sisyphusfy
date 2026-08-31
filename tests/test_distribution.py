"""Tests for release metadata and checksum generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sisyphusfy.distribution import (
    ARTIFACT_TEMPLATE,
    CHECKSUM_FILENAME,
    DEFERRED_TARGETS,
    RAW_BOOTSTRAP_URL,
    RELEASE_TARGETS,
    RELEASES_URL,
    REPOSITORY_URL,
    WEBSITE_URL,
    ReleaseArtifact,
    compute_sha256,
    compute_sha256_bytes,
    generate_checksum_manifest,
    generate_release_metadata,
    get_artifacts_for_version,
    verify_checksum,
    write_release_metadata,
)


class TestConstants:
    def test_repository_url(self) -> None:
        assert REPOSITORY_URL == "https://github.com/lileililiwen/sisyphusfy"

    def test_website_url(self) -> None:
        assert WEBSITE_URL == "https://about.tooosall.uk/"

    def test_releases_url(self) -> None:
        assert RELEASES_URL == "https://github.com/lileililiwen/sisyphusfy/releases"

    def test_raw_bootstrap_url(self) -> None:
        assert "raw.githubusercontent.com" in RAW_BOOTSTRAP_URL
        assert "install.sh" in RAW_BOOTSTRAP_URL

    def test_checksum_filename(self) -> None:
        assert CHECKSUM_FILENAME == "SHA256SUMS.txt"


class TestReleaseArtifact:
    def test_filename_generation(self) -> None:
        artifact = ReleaseArtifact(
            version="0.1.0", platform="linux", arch="x86_64"
        )
        expected = "sisyphusfy-0.1.0-linux-x86_64.tar.gz"
        assert artifact.filename == expected

    def test_url_generation(self) -> None:
        artifact = ReleaseArtifact(
            version="0.1.0", platform="darwin", arch="aarch64"
        )
        assert "download/v0.1.0/" in artifact.url
        assert "sisyphusfy-0.1.0-darwin-aarch64.tar.gz" in artifact.url

    def test_artifact_template(self) -> None:
        result = ARTIFACT_TEMPLATE.format(
            version="1.2.3", platform="linux", arch="x86_64"
        )
        assert result == "sisyphusfy-1.2.3-linux-x86_64.tar.gz"


class TestChecksum:
    def test_compute_sha256(self, tmp_path: Path) -> None:
        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(content)
        assert compute_sha256(file_path) == expected

    def test_compute_sha256_large_file(self, tmp_path: Path) -> None:
        content = b"x" * 100000
        expected = hashlib.sha256(content).hexdigest()
        file_path = tmp_path / "large.bin"
        file_path.write_bytes(content)
        assert compute_sha256(file_path) == expected

    def test_compute_sha256_bytes(self) -> None:
        data = b"test data"
        expected = hashlib.sha256(data).hexdigest()
        assert compute_sha256_bytes(data) == expected

    def test_verify_checksum_success(self, tmp_path: Path) -> None:
        content = b"verified content"
        expected = hashlib.sha256(content).hexdigest()
        file_path = tmp_path / "verify.bin"
        file_path.write_bytes(content)
        assert verify_checksum(file_path, expected) is True

    def test_verify_checksum_failure(self, tmp_path: Path) -> None:
        content = b"wrong content"
        file_path = tmp_path / "wrong.bin"
        file_path.write_bytes(content)
        assert verify_checksum(file_path, "0" * 64) is False


class TestChecksumManifest:
    def test_generate_manifest(self, tmp_path: Path) -> None:
        files = []
        for name in ["a.tar.gz", "b.tar.gz", "c.tar.gz"]:
            path = tmp_path / name
            path.write_bytes(b"content")
            files.append(path)

        manifest = generate_checksum_manifest(files)
        lines = manifest.strip().split("\n")
        assert len(lines) == 3

        for line in lines:
            parts = line.split("  ")
            assert len(parts) == 2
            assert len(parts[0]) == 64

    def test_manifest_sorted(self, tmp_path: Path) -> None:
        files = []
        for name in ["c.tar.gz", "a.tar.gz", "b.tar.gz"]:
            path = tmp_path / name
            path.write_bytes(b"content")
            files.append(path)

        manifest = generate_checksum_manifest(files)
        names = [line.split("  ")[1] for line in manifest.strip().split("\n")]
        assert names == sorted(names)


class TestArtifactsForVersion:
    def test_artifact_count(self) -> None:
        artifacts = get_artifacts_for_version("0.1.0")
        assert len(artifacts) == len(RELEASE_TARGETS)

    def test_artifact_platforms(self) -> None:
        artifacts = get_artifacts_for_version("0.1.0")
        platforms = {a.platform for a in artifacts}
        assert platforms == {"linux", "darwin", "win32"}

    def test_artifact_arches(self) -> None:
        artifacts = get_artifacts_for_version("0.1.0")
        pairs = {(a.platform, a.arch) for a in artifacts}
        assert pairs == {
            (target.platform, target.arch) for target in RELEASE_TARGETS
        }

    def test_deferred_targets_are_not_advertised(self) -> None:
        artifacts = get_artifacts_for_version("0.1.0")
        pairs = {(a.platform, a.arch) for a in artifacts}
        for target in DEFERRED_TARGETS:
            assert (target.platform, target.arch) not in pairs

    def test_artifact_version_in_name(self) -> None:
        artifacts = get_artifacts_for_version("1.2.3")
        for artifact in artifacts:
            assert "1.2.3" in artifact.filename
            assert "1.2.3" in artifact.url


class TestReleaseMetadata:
    def test_metadata_structure(self) -> None:
        metadata = generate_release_metadata("0.1.0")
        assert metadata["version"] == "0.1.0"
        assert metadata["repository"] == REPOSITORY_URL
        assert metadata["website"] == WEBSITE_URL
        assert metadata["releases"] == RELEASES_URL
        assert "artifacts" in metadata
        assert "checksums_url" in metadata

    def test_metadata_artifacts(self) -> None:
        metadata = generate_release_metadata("0.1.0")
        assert len(metadata["artifacts"]) == len(RELEASE_TARGETS)
        for artifact in metadata["artifacts"]:
            assert "filename" in artifact
            assert "platform" in artifact
            assert "arch" in artifact
            assert "url" in artifact

    def test_metadata_json_serializable(self) -> None:
        metadata = generate_release_metadata("0.1.0")
        json_str = json.dumps(metadata)
        parsed = json.loads(json_str)
        assert parsed == metadata

    def test_write_release_metadata(self, tmp_path: Path) -> None:
        output_path = write_release_metadata("0.1.0", tmp_path)
        assert output_path.exists()
        assert output_path.name == "release-0.1.0.json"

        content = json.loads(output_path.read_text())
        assert content["version"] == "0.1.0"
        assert len(content["artifacts"]) == len(RELEASE_TARGETS)
