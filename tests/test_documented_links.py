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

    def test_links_in_proposal(self) -> None:
        proposal = (
            Path(__file__).resolve().parent.parent
            / "openspec"
            / "changes"
            / "add-distribution-and-installers"
            / "proposal.md"
        )
        content = proposal.read_text()
        assert "sisyphusfy.dev" in content
        assert "lileililiwen/sisyphusfy" in content

    def test_links_in_design(self) -> None:
        design = (
            Path(__file__).resolve().parent.parent
            / "openspec"
            / "changes"
            / "add-distribution-and-installers"
            / "design.md"
        )
        content = design.read_text()
        assert REPOSITORY_URL in content
        assert WEBSITE_URL in content
        assert RELEASES_URL in content
        assert RAW_BOOTSTRAP_URL in content
