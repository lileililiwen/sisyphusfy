"""Release artifact metadata and checksum generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

REPOSITORY_URL = "https://github.com/lileililiwen/sisyphusfy"
WEBSITE_URL = "https://sisyphusfy.dev/"
RELEASES_URL = "https://github.com/lileililiwen/sisyphusfy/releases"
RAW_BOOTSTRAP_URL = (
    "https://raw.githubusercontent.com/lileililiwen/sisyphusfy/main/install.sh"
)

SUPPORTED_PLATFORMS: dict[str, list[str]] = {
    "linux": ["x86_64", "aarch64"],
    "darwin": ["x86_64", "aarch64"],
    "win32": ["x86_64"],
}

ARTIFACT_TEMPLATE = "sisyphusfy-{version}-{platform}-{arch}.tar.gz"
CHECKSUM_FILENAME = "SHA256SUMS.txt"


@dataclass
class ReleaseArtifact:
    version: str
    platform: str
    arch: str
    filename: str = field(init=False)
    url: str = field(init=False)

    def __post_init__(self) -> None:
        self.filename = ARTIFACT_TEMPLATE.format(
            version=self.version,
            platform=self.platform,
            arch=self.arch,
        )
        self.url = f"{RELEASES_URL}/download/v{self.version}/{self.filename}"


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest for raw bytes."""
    return hashlib.sha256(data).hexdigest()


def generate_checksum_manifest(
    artifact_paths: list[Path],
) -> str:
    """Generate a SHA256SUMS.txt manifest content."""
    lines: list[str] = []
    for path in sorted(artifact_paths):
        digest = compute_sha256(path)
        lines.append(f"{digest}  {path.name}")
    return "\n".join(lines) + "\n"


def verify_checksum(artifact_path: Path, expected_digest: str) -> bool:
    """Verify an artifact against an expected SHA-256 digest."""
    return compute_sha256(artifact_path) == expected_digest


def get_artifacts_for_version(version: str) -> list[ReleaseArtifact]:
    """Return all release artifacts for a given version."""
    artifacts: list[ReleaseArtifact] = []
    for platform, arches in SUPPORTED_PLATFORMS.items():
        for arch in arches:
            artifacts.append(
                ReleaseArtifact(version=version, platform=platform, arch=arch)
            )
    return artifacts


def generate_release_metadata(version: str) -> dict:
    """Generate release metadata as a dict."""
    artifacts = get_artifacts_for_version(version)
    return {
        "version": version,
        "repository": REPOSITORY_URL,
        "website": WEBSITE_URL,
        "releases": RELEASES_URL,
        "artifacts": [
            {
                "filename": a.filename,
                "platform": a.platform,
                "arch": a.arch,
                "url": a.url,
            }
            for a in artifacts
        ],
        "checksums_url": (
            f"{RELEASES_URL}/download/v{version}/{CHECKSUM_FILENAME}"
        ),
    }


def write_release_metadata(version: str, output_dir: Path) -> Path:
    """Write release metadata JSON file."""
    metadata = generate_release_metadata(version)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"release-{version}.json"
    output_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return output_path
