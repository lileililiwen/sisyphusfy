"""Strict-validation tests for canonical main spec headers."""

from __future__ import annotations

from pathlib import Path

import pytest

SPECS_DIR = Path(__file__).resolve().parent.parent / "openspec" / "specs"

REQUIRED_SECTIONS = ("## Purpose", "## Requirements")


@pytest.fixture
def main_spec_files() -> list[Path]:
    specs: list[Path] = []
    for child in SPECS_DIR.iterdir():
        if child.is_dir() and (child / "spec.md").exists():
            specs.append(child / "spec.md")
    return specs


class TestCanonicalMainSpecHeaders:
    def test_all_main_specs_exist(self) -> None:
        assert SPECS_DIR.exists(), f"specs directory not found: {SPECS_DIR}"
        specs = [d.name for d in SPECS_DIR.iterdir() if d.is_dir() and (d / "spec.md").exists()]
        assert len(specs) >= 3, f"expected at least 3 main specs, found {specs}"

    def test_all_main_specs_have_purpose(self, main_spec_files: list[Path]) -> None:
        for spec_file in main_spec_files:
            content = spec_file.read_text()
            assert "## Purpose" in content, f"{spec_file.name} missing '## Purpose'"

    def test_all_main_specs_have_requirements(self, main_spec_files: list[Path]) -> None:
        for spec_file in main_spec_files:
            content = spec_file.read_text()
            assert "## Requirements" in content, f"{spec_file.name} missing '## Requirements'"

    def test_no_tbd_purpose(self, main_spec_files: list[Path]) -> None:
        for spec_file in main_spec_files:
            content = spec_file.read_text()
            purpose_idx = content.find("## Purpose")
            if purpose_idx >= 0:
                next_section = content.find("\n##", purpose_idx + 10)
                purpose_block = content[purpose_idx:next_section] if next_section >= 0 else content[purpose_idx:]
                assert "TBD" not in purpose_block, f"{spec_file.name} has TBD in Purpose"

    def test_no_added_requirements_header(self, main_spec_files: list[Path]) -> None:
        for spec_file in main_spec_files:
            content = spec_file.read_text()
            assert "## ADDED Requirements" not in content, (
                f"{spec_file.name} still uses '## ADDED Requirements' instead of '## Requirements'"
            )
