"""Test agent adapter registry, selection, and command construction."""

from __future__ import annotations

import pytest

from sisyphusfy.adapters import (
    AdapterConfig,
    AdapterError,
    AdapterRegistry,
    CodeBuddyAdapter,
    FailureClass,
    GenericCommandAdapter,
    ModelChainExhausted,
    OpenCodeAdapter,
    resolve_adapter,
    try_fallback,
)


class TestAdapterRegistry:
    def test_list_builtins(self) -> None:
        reg = AdapterRegistry()
        names = reg.list_names()
        assert "opencode" in names
        assert "codebuddy" in names
        assert "generic" in names

    def test_get_known(self) -> None:
        reg = AdapterRegistry()
        assert reg.get("opencode") is OpenCodeAdapter
        assert reg.get("codebuddy") is CodeBuddyAdapter

    def test_get_unknown(self) -> None:
        reg = AdapterRegistry()
        assert reg.get("nonexistent") is None

    def test_register_custom(self) -> None:
        reg = AdapterRegistry()

        class Dummy:
            pass

        reg.register("dummy", Dummy)
        assert reg.get("dummy") is Dummy
        assert "dummy" in reg.list_names()


class TestResolveAdapter:
    def test_resolve_opencode(self) -> None:
        config = AdapterConfig(name="opencode", model="gpt-4")
        adapter = resolve_adapter(config)
        assert isinstance(adapter, OpenCodeAdapter)

    def test_resolve_codebuddy(self) -> None:
        config = AdapterConfig(name="codebuddy")
        adapter = resolve_adapter(config)
        assert isinstance(adapter, CodeBuddyAdapter)

    def test_resolve_generic(self) -> None:
        config = AdapterConfig(name="generic", command=["my-cli", "run"])
        adapter = resolve_adapter(config)
        assert isinstance(adapter, GenericCommandAdapter)
        assert adapter.command == ["my-cli", "run"]

    def test_resolve_unknown_raises(self) -> None:
        config = AdapterConfig(name="nope")
        with pytest.raises(AdapterError, match="unknown adapter"):
            resolve_adapter(config)


class TestOpenCodeAdapter:
    def test_build_command_no_model(self) -> None:
        adapter = OpenCodeAdapter()
        cmd = adapter.build_command("/tmp/work", "hello")
        assert cmd == ["opencode", "run", "hello"]

    def test_build_command_with_model(self) -> None:
        adapter = OpenCodeAdapter(model="claude-3")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert cmd[0] == "opencode"
        assert cmd[1] == "run"
        assert "--model" in cmd
        assert "claude-3" in cmd
        assert "hello" in cmd

    def test_supports_model(self) -> None:
        adapter = OpenCodeAdapter()
        assert adapter.supports_model("any-model") is True


class TestCodeBuddyAdapter:
    def test_build_command_no_model(self) -> None:
        adapter = CodeBuddyAdapter()
        cmd = adapter.build_command("/tmp/work", "hello")
        assert cmd == ["codebuddy", "-p", "hello"]

    def test_build_command_with_model(self) -> None:
        adapter = CodeBuddyAdapter(model="gpt-4")
        cmd = adapter.build_command("/tmp/work", "hello")
        assert cmd[0] == "codebuddy"
        assert "-p" in cmd
        assert "--model" in cmd
        assert "gpt-4" in cmd
        assert "hello" in cmd


class TestGenericCommandAdapter:
    def test_build_command(self) -> None:
        adapter = GenericCommandAdapter(command=["run-agent", "--flag"])
        cmd = adapter.build_command("/tmp/work", "hello")
        assert cmd == ["run-agent", "--flag"]

    def test_classify_quota_failure(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])
        cls = adapter.classify_failure(1, "Error: quota exceeded")
        assert cls == FailureClass.RETRYABLE_PROVIDER

    def test_classify_rate_limit(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])
        cls = adapter.classify_failure(1, "429 Too Many Requests")
        assert cls == FailureClass.RETRYABLE_PROVIDER

    def test_classify_signal_exit(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])
        cls = adapter.classify_failure(-1, "")
        assert cls == FailureClass.RETRYABLE_PROCESS

    def test_classify_non_retryable(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])
        cls = adapter.classify_failure(1, "File not found")
        assert cls == FailureClass.NON_RETRYABLE


class TestTryFallback:
    def test_first_model_succeeds(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])

        def run_fn(model: str = "default") -> object:
            class R:
                exit_status = 0
                stderr = ""
            return R()

        result, attempts = try_fallback(
            adapter, ["model-a", "model-b"], "/tmp", None, run_fn
        )
        assert result.exit_status == 0
        assert attempts == ["model-a"]

    def test_fallback_on_provider_failure(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])
        call_count = 0

        def run_fn(model: str = "default") -> object:
            nonlocal call_count
            call_count += 1

            class R:
                exit_status = 1
                stderr = "quota exceeded" if model == "model-a" else ""
                timed_out = False
            return R()

        _result, attempts = try_fallback(
            adapter, ["model-a", "model-b"], "/tmp", None, run_fn
        )
        assert attempts == ["model-a", "model-b"]

    def test_non_retryable_stops(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])

        def run_fn(model: str = "default") -> object:
            class R:
                exit_status = 1
                stderr = "permission denied"
                timed_out = False
            return R()

        _result, attempts = try_fallback(
            adapter, ["model-a", "model-b"], "/tmp", None, run_fn
        )
        assert attempts == ["model-a"]

    def test_exhausted_models(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])

        def run_fn(model: str = "default") -> object:
            class R:
                exit_status = 1
                stderr = "quota exceeded"
                timed_out = False
            return R()

        with pytest.raises(ModelChainExhausted) as exc_info:
            try_fallback(adapter, ["model-a", "model-b"], "/tmp", None, run_fn)
        assert exc_info.value.attempts == ["model-a", "model-b"]
