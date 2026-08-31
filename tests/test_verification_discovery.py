"""Tests for marker-aware verification discovery."""

from __future__ import annotations

from pathlib import Path

from sisyphusfy.config import (
    VerificationDetectionError,
    VerificationSource,
    _detect_javascript,
    discover_verification_command,
    find_verification_command,
    resolve_verification,
)


def _available(*names: str):
    return lambda name: name in names


class TestDotnetDiscovery:
    def test_solution_marker_selects_dotnet_test(self, tmp_path: Path) -> None:
        (tmp_path / "OpenLearning.sln").write_text("")
        resolution = discover_verification_command(str(tmp_path), _available("dotnet"))
        assert resolution.source is VerificationSource.DISCOVERED
        assert resolution.detector == "dotnet"
        assert resolution.command == ["dotnet", "test", "OpenLearning.sln"]

    def test_project_marker_when_no_solution(self, tmp_path: Path) -> None:
        (tmp_path / "Api.csproj").write_text("<Project />")
        resolution = discover_verification_command(str(tmp_path), _available("dotnet"))
        assert resolution.command == ["dotnet", "test", "Api.csproj"]

    def test_dotnet_not_installed_is_not_selected(self, tmp_path: Path) -> None:
        (tmp_path / "OpenLearning.sln").write_text("")
        resolution = discover_verification_command(str(tmp_path), _available())
        assert resolution.source is VerificationSource.UNAVAILABLE
        assert resolution.command == []


class TestNoUnrelatedMakeVerifier:
    def test_make_alone_does_not_select_make_test(self, tmp_path: Path) -> None:
        """The regression: `make` on PATH must never imply `make test`."""
        (tmp_path / "OpenLearning.sln").write_text("")
        resolution = discover_verification_command(
            str(tmp_path), _available("dotnet", "make")
        )
        assert resolution.command == ["dotnet", "test", "OpenLearning.sln"]

    def test_empty_project_is_not_verified_by_installed_tool(self, tmp_path: Path) -> None:
        resolution = discover_verification_command(
            str(tmp_path), _available("pytest", "make", "cargo")
        )
        assert resolution.source is VerificationSource.UNAVAILABLE
        assert find_verification_command(str(tmp_path)) is None


class TestMakefileDiscovery:
    def test_declared_test_target_selects_make_test(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("build:\n\tcc main.c\n\ntest:\n\t./run-tests\n")
        resolution = discover_verification_command(str(tmp_path), _available("make"))
        assert resolution.detector == "make"
        assert resolution.command == ["make", "test"]

    def test_makefile_without_test_target_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("build:\n\tcc main.c\n")
        resolution = discover_verification_command(str(tmp_path), _available("make"))
        assert resolution.source is VerificationSource.UNAVAILABLE

    def test_make_missing_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("test:\n\ttrue\n")
        resolution = discover_verification_command(str(tmp_path), _available())
        assert resolution.source is VerificationSource.UNAVAILABLE


class TestEcosystemDiscovery:
    def test_rust_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "app"\n')
        resolution = discover_verification_command(str(tmp_path), _available("cargo"))
        assert resolution.command == ["cargo", "test"]

    def test_python_project_marker(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'app'\n")
        resolution = discover_verification_command(str(tmp_path), _available("pytest"))
        assert resolution.command == ["pytest"]

    def test_python_tests_directory(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        resolution = discover_verification_command(str(tmp_path), _available("pytest"))
        assert resolution.command == ["pytest"]

    def test_javascript_test_script(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest run"}}')
        resolution = discover_verification_command(str(tmp_path), _available("npm"))
        assert resolution.command == ["npm", "test"]

    def test_javascript_without_test_script_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"scripts": {"build": "tsc"}}')
        resolution = discover_verification_command(
            str(tmp_path), _available("npm", "make")
        )
        assert resolution.source is VerificationSource.UNAVAILABLE

    def test_flutter_marker(self, tmp_path: Path) -> None:
        (tmp_path / "pubspec.yaml").write_text("name: app\n")
        resolution = discover_verification_command(str(tmp_path), _available("flutter"))
        assert resolution.command == ["flutter", "test"]


class TestDetectorPrecedence:
    def test_dotnet_wins_over_rust_python_and_make(self, tmp_path: Path) -> None:
        (tmp_path / "App.sln").write_text("")
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "Makefile").write_text("test:\n\ttrue\n")
        resolution = discover_verification_command(
            str(tmp_path), _available("dotnet", "cargo", "pytest", "make")
        )
        assert resolution.command == ["dotnet", "test", "App.sln"]

    def test_missing_executable_falls_to_next_marker(self, tmp_path: Path) -> None:
        (tmp_path / "App.sln").write_text("")
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        resolution = discover_verification_command(str(tmp_path), _available("cargo"))
        assert resolution.command == ["cargo", "test"]

    def test_detection_order_is_stable(self) -> None:
        from sisyphusfy.config import DETECTORS

        assert [name for name, _ in DETECTORS] == [
            "dotnet",
            "rust",
            "python",
            "javascript",
            "flutter",
            "make",
        ]


class TestDetectionErrorsDoNotFallThrough:
    def test_malformed_package_json_blocks_later_ecosystems(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{not json")
        (tmp_path / "Makefile").write_text("test:\n\ttrue\n")
        resolution = discover_verification_command(str(tmp_path), _available("npm", "make"))
        assert resolution.source is VerificationSource.UNAVAILABLE
        assert resolution.detector == "javascript"
        assert "package.json" in resolution.detail

    def test_detector_raises_on_unreadable_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{")
        try:
            _detect_javascript(tmp_path, _available("npm"))
        except VerificationDetectionError:
            pass
        else:  # pragma: no cover - guard against a silent success
            raise AssertionError("malformed package.json must raise")


class TestExplicitConfiguration:
    def test_configured_command_wins_over_markers(self, tmp_path: Path) -> None:
        (tmp_path / "App.sln").write_text("")
        resolution = resolve_verification(["dotnet", "test", "--filter", "Fast"], str(tmp_path))
        assert resolution.source is VerificationSource.CONFIGURED
        assert resolution.command == ["dotnet", "test", "--filter", "Fast"]

    def test_configured_command_is_not_replaced_when_absent(self, tmp_path: Path) -> None:
        resolution = resolve_verification(["./scripts/smoke.sh"], str(tmp_path), _available())
        assert resolution.source is VerificationSource.CONFIGURED
        assert resolution.available is True

    def test_empty_configuration_falls_back_to_discovery(self, tmp_path: Path) -> None:
        (tmp_path / "App.sln").write_text("")
        resolution = resolve_verification([], str(tmp_path), _available("dotnet"))
        assert resolution.source is VerificationSource.DISCOVERED

    def test_unavailable_resolution_reports_detail(self, tmp_path: Path) -> None:
        resolution = resolve_verification(None, str(tmp_path), _available())
        assert resolution.source is VerificationSource.UNAVAILABLE
        assert resolution.available is False
        assert resolution.detail
        assert resolution.to_dict()["available"] is False
