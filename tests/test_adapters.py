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

    def test_classify_combined_output_marks_retryable(self) -> None:
        """The classifier sees the bounded combined stdout+stderr.

        Under the new contract ``classify_failure`` receives the combined
        output, so a retryable marker in either stream classifies as
        ``RETRYABLE_PROVIDER`` regardless of which stream it was on.
        """
        adapter = GenericCommandAdapter(command=["x"])
        cls = adapter.classify_failure(1, "rate limit on stdout\n")
        assert cls == FailureClass.RETRYABLE_PROVIDER

    def test_classify_combined_output_marks_non_retryable(self) -> None:
        """A task-level failure stays non-retryable in combined output.

        The classifier must not invent a retryable classification from
        arbitrary text; only configured markers classify as retryable.
        """
        adapter = GenericCommandAdapter(command=["x"])
        cls = adapter.classify_failure(1, "permission denied on stdout\n")
        assert cls == FailureClass.NON_RETRYABLE


class TestOpenCodeAdapterCombinedOutput:
    def test_classify_quota_via_combined_output(self) -> None:
        adapter = OpenCodeAdapter()
        cls = adapter.classify_failure(1, "quota exceeded on stdout")
        assert cls == FailureClass.RETRYABLE_PROVIDER

    def test_classify_signal_exit(self) -> None:
        adapter = OpenCodeAdapter()
        cls = adapter.classify_failure(-1, "")
        assert cls == FailureClass.RETRYABLE_PROCESS


class TestCodeBuddyAdapterCombinedOutput:
    def test_classify_quota_via_combined_output(self) -> None:
        adapter = CodeBuddyAdapter()
        cls = adapter.classify_failure(1, "quota exceeded on stdout")
        assert cls == FailureClass.RETRYABLE_PROVIDER


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

    def test_exhausted_models_carry_the_last_result(self) -> None:
        adapter = GenericCommandAdapter(command=["x"])

        def run_fn(model: str = "default") -> object:
            class R:
                exit_status = 1
                stderr = "quota exceeded"
                timed_out = False
            return R()

        with pytest.raises(ModelChainExhausted) as exc_info:
            try_fallback(adapter, ["model-a", "model-b"], "/tmp", None, run_fn)
        assert exc_info.value.last_result is not None
        assert exc_info.value.last_result.exit_status == 1


class TestParseError:
    ENVELOPE = """\
Error: {
"name": "UnknownError",
"data": {
"message": "Unexpected server error. Check server logs for details.",
"ref": "err_cbece906"
}
}
"""

    def test_extracts_name_message_and_reference(self) -> None:
        error = OpenCodeAdapter().parse_error(self.ENVELOPE)
        assert error is not None
        assert error.name == "UnknownError"
        assert error.message == "Unexpected server error. Check server logs for details."
        assert error.reference == "err_cbece906"

    def test_finds_an_envelope_inside_other_output(self) -> None:
        output = f"reading tasks.md\n{self.ENVELOPE}\nmore output\n"
        error = OpenCodeAdapter().parse_error(output)
        assert error is not None
        assert error.reference == "err_cbece906"

    def test_returns_none_without_an_envelope(self) -> None:
        assert OpenCodeAdapter().parse_error("all tests passed") is None

    def test_returns_none_for_malformed_json(self) -> None:
        assert OpenCodeAdapter().parse_error('Error: {"name": "UnknownError",') is None
        assert OpenCodeAdapter().parse_error('{"name": }') is None

    def test_returns_none_for_a_non_error_object(self) -> None:
        assert OpenCodeAdapter().parse_error('{"result": "ok"}') is None

    def test_ignores_braces_inside_strings(self) -> None:
        output = 'Error: {"name": "X", "data": {"message": "unbalanced } brace"}}'
        error = OpenCodeAdapter().parse_error(output)
        assert error is not None
        assert error.message == "unbalanced } brace"

    def test_every_builtin_exposes_parse_error(self) -> None:
        adapters = [
            OpenCodeAdapter(),
            CodeBuddyAdapter(),
            GenericCommandAdapter(command=["x"]),
        ]
        for adapter in adapters:
            error = adapter.parse_error(self.ENVELOPE)
            assert error is not None, f"{type(adapter).__name__} has no parse_error"
            assert error.reference == "err_cbece906"

    def test_agent_error_to_dict(self) -> None:
        from sisyphusfy.adapters import AgentError

        assert AgentError(name="N").to_dict() == {"name": "N"}
        assert AgentError().to_dict() == {}
        assert AgentError(
            name="UnknownError", message="boom", reference="err_1"
        ).to_dict() == {
            "name": "UnknownError",
            "message": "boom",
            "reference": "err_1",
        }
