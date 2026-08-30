"""Tests for documented repository, website, and release links."""

from __future__ import annotations

from pathlib import Path

from sisyphusfy.distribution import (
    RAW_BOOTSTRAP_URL,
    RELEASES_URL,
    REPOSITORY_URL,
    WEBSITE_URL,
)


class TestDocumentedLinks:
    def test_repository_url_format(self) -> None:
        assert REPOSITORY_URL.startswith("https://github.com/")
        assert REPOSITORY_URL.endswith("sisyphusfy")

    def test_website_url_format(self) -> None:
        assert WEBSITE_URL.startswith("https://")
        assert WEBSITE_URL.endswith("/")

    def test_releases_url_format(self) -> None:
        assert RELEASES_URL.startswith("https://github.com/")
        assert "/releases" in RELEASES_URL

    def test_raw_bootstrap_url_format(self) -> None:
        assert RAW_BOOTSTRAP_URL.startswith("https://raw.githubusercontent.com/")
        assert "install.sh" in RAW_BOOTSTRAP_URL

    def test_links_in_readme(self) -> None:
        readme = Path(__file__).resolve().parent.parent / "README.md"
        content = readme.read_text()
        assert REPOSITORY_URL in content or "github.com/lileililiwen/sisyphusfy" in content

    def test_links_in_canonical_distribution_spec(self) -> None:
        # Archive-safe: read the canonical main spec, never an active change dir.
        spec = (
            Path(__file__).resolve().parent.parent
            / "openspec"
            / "specs"
            / "distribution"
            / "spec.md"
        )
        content = spec.read_text()
        assert REPOSITORY_URL in content
        assert WEBSITE_URL in content
        assert "lileililiwen/sisyphusfy" in content

    def test_canonical_links_present_when_archived(self) -> None:
        # Even after the change moves to archive/, the canonical links must be
        # locatable from stable artifacts (README or canonical main spec).
        repo_root = Path(__file__).resolve().parent.parent
        readme = repo_root / "README.md"
        spec = repo_root / "openspec" / "specs" / "distribution" / "spec.md"
        found = []
        if readme.exists():
            found.append("github.com/lileililiwen/sisyphusfy" in readme.read_text())
        if spec.exists():
            spec_content = spec.read_text()
            found.append("sisyphusfy.dev" in spec_content)
            found.append("lileililiwen/sisyphusfy" in spec_content)
        assert any(found), "canonical project links not found in stable artifacts"
