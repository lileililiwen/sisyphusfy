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

@dataclass(frozen=True)
class ReleaseTarget:
    """A platform/architecture pair and the CI runner that builds it natively."""

    platform: str
    arch: str
    runner: str

    @property
    def slug(self) -> str:
        return f"{self.platform}-{self.arch}"


# The native architecture produced by each CI runner label. A release target is
# only honest when its runner produces that architecture without emulation.
RUNNER_NATIVE_ARCH: dict[str, str] = {
    "ubuntu-latest": "x86_64",
    "macos-13": "x86_64",
    "macos-14": "aarch64",
    "windows-latest": "x86_64",
}

RELEASE_TARGETS: tuple[ReleaseTarget, ...] = (
    ReleaseTarget("linux", "x86_64", "ubuntu-latest"),
    ReleaseTarget("darwin", "x86_64", "macos-13"),
    ReleaseTarget("darwin", "aarch64", "macos-14"),
    ReleaseTarget("win32", "x86_64", "windows-latest"),
)

# Deferred until an aarch64 runner or a verified cross-compilation process
# exists. Deferred targets must not appear in release metadata, installers, or
# the CI matrix.
DEFERRED_TARGETS: tuple[ReleaseTarget, ...] = (ReleaseTarget("linux", "aarch64", ""),)

ARTIFACT_TEMPLATE = "sisyphusfy-{version}-{platform}-{arch}.tar.gz"
CHECKSUM_FILENAME = "SHA256SUMS.txt"


def _supported_platforms() -> dict[str, list[str]]:
    platforms: dict[str, list[str]] = {}
    for target in RELEASE_TARGETS:
        platforms.setdefault(target.platform, []).append(target.arch)
    return platforms


SUPPORTED_PLATFORMS: dict[str, list[str]] = _supported_platforms()


def is_supported(platform: str, arch: str) -> bool:
    """Report whether a prebuilt artifact is published for this pair."""
    return arch in SUPPORTED_PLATFORMS.get(platform, [])


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
