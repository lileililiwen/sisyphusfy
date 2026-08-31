"""Documentation contracts for the public configuration, adapter, and security surfaces."""

from __future__ import annotations

from pathlib import Path

from sisyphusfy.config import DEFAULT_CONFIG, SisyphusConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
CONFIGURATION = DOCS / "configuration.md"
ADAPTERS = DOCS / "adapters.md"
EXAMPLES = DOCS / "examples.md"
CI = DOCS / "ci.md"
SECURITY = DOCS / "security.md"

CONFIG_FIELDS = tuple(SisyphusConfig().to_dict().keys())


class TestConfigurationDocumentation:
    def test_documentation_exists(self) -> None:
        assert CONFIGURATION.exists()

    def test_every_field_is_documented(self) -> None:
        content = CONFIGURATION.read_text()
        for field in CONFIG_FIELDS:
            assert f"`{field}`" in content, f"configuration field undocumented: {field}"

    def test_documented_fields_match_implementation(self) -> None:
        content = CONFIGURATION.read_text()
        documented = {
            name
            for name in CONFIG_FIELDS
            if f"`{name}`" in content
        }
        assert documented == set(CONFIG_FIELDS)
        assert set(CONFIG_FIELDS) == set(DEFAULT_CONFIG)

    def test_types_and_defaults_are_documented(self) -> None:
        content = CONFIGURATION.read_text()
        assert "Type" in content
        assert "Default" in content
        assert "Safety" in content
        for value in DEFAULT_CONFIG.values():
            if isinstance(value, bool):
                rendered = "true" if value else "false"
            elif isinstance(value, list):
                rendered = "[]"
            else:
                rendered = str(value)
            assert rendered in content or f"`{rendered}`" in content

    def test_precedence_is_documented(self) -> None:
        content = CONFIGURATION.read_text()
        assert "Precedence" in content or "precedence" in content
        assert "~/.config/sisyphusfy/config.toml" in content
        assert ".sisyphusfy.toml" in content
        assert "CLI" in content

    def test_safety_behavior_is_documented(self) -> None:
        content = CONFIGURATION.read_text()
        assert "commit_allowed_files" in content
        assert "escape" in content.lower()


class TestAdapterDocumentation:
    def test_documentation_exists(self) -> None:
        assert ADAPTERS.exists()

    def test_protocol_methods_are_documented(self) -> None:
        content = ADAPTERS.read_text()
        for method in ("build_command", "supports_model", "classify_failure"):
            assert method in content, f"adapter protocol method undocumented: {method}"

    def test_registration_path_is_documented(self) -> None:
        content = ADAPTERS.read_text()
        assert "AdapterRegistry" in content
        assert ".register(" in content

    def test_command_construction_rules_are_documented(self) -> None:
        content = ADAPTERS.read_text()
        assert "list" in content
        assert "shell" in content.lower()

    def test_model_behavior_is_documented(self) -> None:
        content = ADAPTERS.read_text()
        assert "model_chain" in content
        assert "ModelChainExhausted" in content

    def test_failure_classification_is_documented(self) -> None:
        content = ADAPTERS.read_text()
        for failure_class in ("RETRYABLE_PROVIDER", "RETRYABLE_PROCESS", "NON_RETRYABLE"):
            assert failure_class in content

    def test_workflow_adapters_are_documented(self) -> None:
        content = ADAPTERS.read_text()
        for method in ("has_work", "is_complete", "explain", "snapshot", "reload"):
            assert method in content
        for adapter_type in ("markdown", "json", "external", "openspec"):
            assert adapter_type in content


class TestExampleDocumentation:
    def test_documentation_exists(self) -> None:
        assert EXAMPLES.exists()

    def test_requested_ecosystems_are_covered(self) -> None:
        content = EXAMPLES.read_text()
        for ecosystem in ("Python", "Rust", "JavaScript", "Flutter", ".NET"):
            assert f"## {ecosystem}" in content, f"missing end-to-end example: {ecosystem}"

    def test_examples_are_minimal_and_complete(self) -> None:
        content = EXAMPLES.read_text()
        assert content.count("```toml") >= 5
        assert "verification_command" in content
        assert "sisyphusfy run" in content


class TestCiAndSecurityDocumentation:
    def test_documentation_exists(self) -> None:
        assert CI.exists()
        assert SECURITY.exists()

    def test_ci_examples_exist(self) -> None:
        content = CI.read_text()
        assert "runs-on:" in content
        assert "sisyphusfy run --dry-run" in content
        assert "--json" in content

    def test_security_covers_every_command_source(self) -> None:
        content = SECURITY.read_text()
        for source in (
            "Agent",
            "Verification",
            "Workflow check",
            "Workflow validation",
            "Archive hook",
            "Commit hook",
        ):
            assert source in content, f"command source undocumented: {source}"

    def test_security_documents_safeguards(self) -> None:
        content = SECURITY.read_text()
        for safeguard in ("timeout", "working directory", "dry-run", "allowlist"):
            assert safeguard.lower() in content.lower()

    def test_security_states_user_controlled_execution(self) -> None:
        content = SECURITY.read_text()
        assert "user-controlled" in content.lower()


class TestDocumentationIsDiscoverable:
    def test_readme_links_to_docs(self) -> None:
        readme = REPO_ROOT / "README.md"
        content = readme.read_text()
        for doc in ("configuration.md", "adapters.md", "examples.md", "ci.md", "security.md"):
            assert doc in content, f"README does not link to {doc}"
