"""Tests for configuration discovery, precedence, and init."""

from __future__ import annotations

from pathlib import Path

import pytest

from sisyphusfy.config import (
    SisyphusConfig,
    apply_cli_overrides,
    discover_handoff_path,
    discover_openspec_change,
    discover_task_path,
    find_verification_command,
    init_project_config,
    load_config,
)


class TestLoadConfig:
    def test_defaults_when_no_config(self, tmp_path: Path) -> None:
        config = load_config(str(tmp_path))
        assert config.adapter == "opencode"
        assert config.model_chain == []
        assert config.workflow_type == "markdown"
        assert config.max_iterations == 10
        assert config.agent_timeout == 60.0
        assert config.handoff_path == "HANDOFF.md"
        assert config.archive_enabled is False
        assert config.commit_enabled is False

    def test_project_config_overrides_defaults(self, tmp_path: Path) -> None:
        (tmp_path / ".sisyphusfy.toml").write_text(
            'adapter = "codebuddy"\nmax_iterations = 5\n'
        )
        config = load_config(str(tmp_path))
        assert config.adapter == "codebuddy"
        assert config.max_iterations == 5
        assert config.model_chain == []

    def test_invalid_toml_uses_defaults(self, tmp_path: Path) -> None:
        (tmp_path / ".sisyphusfy.toml").write_text("{{{{invalid")
        config = load_config(str(tmp_path))
        assert config.adapter == "opencode"

    def test_missing_config_file_uses_defaults(self, tmp_path: Path) -> None:
        config = load_config(str(tmp_path))
        assert config.adapter == "opencode"


class TestInitProjectConfig:
    def test_creates_config_file(self, tmp_path: Path) -> None:
        config_path = init_project_config(str(tmp_path))
        assert config_path.exists()
        content = config_path.read_text()
        assert "adapter" in content
        assert "opencode" in content

    def test_creates_valid_toml(self, tmp_path: Path) -> None:
        config_path = init_project_config(str(tmp_path))
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        assert data["adapter"] == "opencode"
        assert data["max_iterations"] == 10

    def test_fails_without_force_when_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".sisyphusfy.toml").write_text("existing")
        with pytest.raises(FileExistsError):
            init_project_config(str(tmp_path))

    def test_force_overwrites_existing(self, tmp_path: Path) -> None:
        (tmp_path / ".sisyphusfy.toml").write_text("old content")
        config_path = init_project_config(str(tmp_path), force=True)
        content = config_path.read_text()
        assert "opencode" in content
        assert "old content" not in content


class TestApplyCliOverrides:
    def test_overrides_adapter(self) -> None:
        config = SisyphusConfig()
        config = apply_cli_overrides(config, adapter="codebuddy")
        assert config.adapter == "codebuddy"

    def test_overrides_max_iterations(self) -> None:
        config = SisyphusConfig()
        config = apply_cli_overrides(config, max_iterations=20)
        assert config.max_iterations == 20

    def test_none_values_not_applied(self) -> None:
        config = SisyphusConfig()
        original = config.adapter
        config = apply_cli_overrides(config, adapter=None)
        assert config.adapter == original


class TestDiscoverTaskPath:
    def test_finds_tasks_md(self, tmp_path: Path) -> None:
        (tmp_path / "tasks.md").write_text("- [ ] task 1\n")
        result = discover_task_path(str(tmp_path))
        assert result is not None
        assert result.endswith("tasks.md")

    def test_finds_TASKS_md(self, tmp_path: Path) -> None:
        (tmp_path / "TASKS.md").write_text("- [ ] task 1\n")
        result = discover_task_path(str(tmp_path))
        assert result is not None
        assert result.endswith("TASKS.md")

    def test_returns_none_when_no_task(self, tmp_path: Path) -> None:
        result = discover_task_path(str(tmp_path))
        assert result is None

    def test_openspec_change_path(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "openspec" / "changes" / "my-change"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [ ] task 1\n")
        result = discover_task_path(str(tmp_path), change="my-change")
        assert result is not None
        assert "my-change" in result
        assert result.endswith("tasks.md")

    def test_openspec_change_not_found(self, tmp_path: Path) -> None:
        result = discover_task_path(str(tmp_path), change="nonexistent")
        assert result is None


class TestDiscoverHandoffPath:
    def test_finds_HANDOFF_md(self, tmp_path: Path) -> None:
        (tmp_path / "HANDOFF.md").write_text("handoff\n")
        result = discover_handoff_path(str(tmp_path))
        assert result is not None
        assert "HANDOFF.md" in result

    def test_returns_none_when_no_handoff(self, tmp_path: Path) -> None:
        result = discover_handoff_path(str(tmp_path))
        assert result is None

    def test_respects_config_handoff_path(self, tmp_path: Path) -> None:
        (tmp_path / "custom-handoff.md").write_text("handoff\n")
        config = SisyphusConfig(handoff_path="custom-handoff.md")
        result = discover_handoff_path(str(tmp_path), config)
        assert result is not None
        assert "custom-handoff.md" in result


class TestDiscoverOpenSpecChange:
    def test_finds_active_change(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "openspec" / "changes" / "my-change"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [ ] task 1\n")
        result = discover_openspec_change(str(tmp_path))
        assert result is not None
        assert "my-change" in result

    def test_ignores_complete_change(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "openspec" / "changes" / "done-change"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [x] done\n")
        result = discover_openspec_change(str(tmp_path))
        assert result is None

    def test_finds_named_change(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "openspec" / "changes" / "target-change"
        change_dir.mkdir(parents=True)
        (change_dir / "tasks.md").write_text("- [ ] task 1\n")
        result = discover_openspec_change(str(tmp_path), change="target-change")
        assert result is not None
        assert "target-change" in result

    def test_returns_none_when_no_changes_dir(self, tmp_path: Path) -> None:
        result = discover_openspec_change(str(tmp_path))
        assert result is None


class TestFindVerificationCommand:
    def test_finds_pytest_if_available(self, tmp_path: Path) -> None:
        result = find_verification_command(str(tmp_path))
        if result is not None:
            assert result[0] in ("pytest", "make", "cargo")
