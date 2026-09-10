"""Test fallback captures every command and proves selected-model replacement."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from sisyphusfy.adapters import (
    AdapterConfig,
    GenericCommandAdapter,
    ModelChainExhausted,
    try_fallback,
)
from sisyphusfy.loop import (
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    run_loop,
)


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestFallbackCommandCapture:
    def test_each_model_attempt_captures_command(self, tmp_path: Path) -> None:
        adapter = GenericCommandAdapter(command=["fake-agent"])
        captured: list[str] = []

        def run_fn(model: str = "default") -> object:
            captured.append(model)

            class R:
                exit_status = 1
                stderr = "quota exceeded"
                timed_out = False
            return R()

        try:
            try_fallback(adapter, ["model-a", "model-b", "model-c"], "/tmp", None, run_fn)
        except ModelChainExhausted:
            pass

        assert captured == ["model-a", "model-b", "model-c"]

    def test_fresh_command_per_model(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        log = tmp_path / "commands.log"

        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import sys, os
            from pathlib import Path
            model = os.environ.get("AGENT_MODEL", "none")
            cmd_str = " ".join(sys.argv)
            with open("{log}", "a") as f:
                f.write(f"model={{model}} cmd={{cmd_str}}\\n")
            if model == "model-a":
                print("quota exceeded", file=sys.stderr)
                sys.exit(1)
            task = Path(sys.argv[1])
            task.write_text("- [x] work\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
            model_chain=["model-a", "model-b"],
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        assert "model-a" in result.model_attempts
        assert "model-b" in result.model_attempts

        log_content = log.read_text()
        assert "model-a" in log_content
        assert "model-b" in log_content


class TestFallbackModelReplacement:
    def test_fallback_uses_next_model_not_original(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        env_log = tmp_path / "env.log"

        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import sys, os
            from pathlib import Path
            model = os.environ.get("AGENT_MODEL", "none")
            with open("{env_log}", "a") as f:
                f.write(model + "\\n")
            if model == "first":
                print("rate limit", file=sys.stderr)
                sys.exit(1)
            task = Path(sys.argv[-1])
            task.write_text("- [x] work\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
            model_chain=["first", "second"],
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.model_attempts == ["first", "second"]

        env_content = env_log.read_text().strip().splitlines()
        assert env_content[0] == "first"
        assert env_content[1] == "second"
        assert "first" not in env_content[1:]

    def test_non_retryable_stops_immediately(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        env_log = tmp_path / "env.log"

        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import sys, os
            from pathlib import Path
            model = os.environ.get("AGENT_MODEL", "none")
            with open("{env_log}", "a") as f:
                f.write(model + "\\n")
            print("file not found", file=sys.stderr)
            sys.exit(1)
            """,
        )

        config = LoopConfig(
            agent_command=cmd + [str(task_path)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
            model_chain=["model-a", "model-b"],
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.AGENT_FAILED
        env_content = env_log.read_text().strip().splitlines()
        assert env_content == ["model-a"]
        assert result.model_attempts == ["model-a"]


class TestFallbackClassifiesCombinedOutput:
    def test_quota_on_stdout_advances_chain(self, tmp_path: Path) -> None:
        """A retryable marker on stdout alone still triggers fallback.

        Some agents print provider errors on stdout, not stderr. The
        classifier must see both streams so a stdout-only quota error does
        not stop the loop as ``agent_failed`` before trying the next model.
        """
        adapter = GenericCommandAdapter(command=["x"])
        attempts: list[str] = []

        def run_fn(model: str = "default") -> object:
            attempts.append(model)

            class R:
                exit_status = 1
                stdout = "quota exceeded" if model == "model-a" else ""
                stderr = ""
                timed_out = False
            return R()

        result, returned_attempts = try_fallback(
            adapter, ["model-a", "model-b"], "/tmp", None, run_fn
        )
        assert returned_attempts == ["model-a", "model-b"]
        assert result.stdout == ""

    def test_quota_split_across_streams_advances_chain(self) -> None:
        """Markers split across stdout and stderr still classify as retryable.

        The combined output is the concatenation of stdout and stderr, so
        a provider error that the agent prints across both streams (for
        example a header on stdout and a rate-limit message on stderr) is
        still classified as retryable.
        """
        adapter = GenericCommandAdapter(command=["x"])
        attempts: list[str] = []

        def run_fn(model: str = "default") -> object:
            attempts.append(model)

            class R:
                exit_status = 0 if model == "model-b" else 1
                stdout = "Error: 429" if model == "model-a" else ""
                stderr = "rate limit reached" if model == "model-a" else ""
                timed_out = False
            return R()

        result, returned_attempts = try_fallback(
            adapter, ["model-a", "model-b"], "/tmp", None, run_fn
        )
        assert returned_attempts == ["model-a", "model-b"]
        assert result.exit_status == 0

    def test_non_retryable_stops_chain_with_no_retryable_classification(self) -> None:
        """A task-level failure stops the chain after one attempt.

        The classifier must not invent a retryable classification from
        arbitrary output; only configured markers classify as retryable.
        """
        adapter = GenericCommandAdapter(command=["x"])
        attempts: list[str] = []

        def run_fn(model: str = "default") -> object:
            attempts.append(model)

            class R:
                exit_status = 1
                stdout = "permission denied"
                stderr = ""
                timed_out = False
            return R()

        _result, returned_attempts = try_fallback(
            adapter, ["model-a", "model-b"], "/tmp", None, run_fn
        )
        assert returned_attempts == ["model-a"]


class TestFallbackUnsupportedModel:
    def test_unsupported_model_is_skipped(self) -> None:
        """A model rejected by ``supports_model`` is skipped, not failed.

        The skipped model must not appear in the attempt list and must not
        call ``run_fn``. The chain advances to the next supported model.
        """
        adapter = GenericCommandAdapter(command=["x"])
        adapter.supports_model = lambda m: m != "skip-me"  # type: ignore[method-assign]
        attempts: list[str] = []

        def run_fn(model: str = "default") -> object:
            attempts.append(model)

            class R:
                exit_status = 1
                stdout = ""
                stderr = "quota exceeded"
                timed_out = False
            return R()

        try:
            try_fallback(
                adapter,
                ["model-a", "skip-me", "model-b"],
                "/tmp",
                None,
                run_fn,
            )
        except ModelChainExhausted as exc:
            returned_attempts = exc.attempts
        else:
            returned_attempts = []

        assert returned_attempts == ["model-a", "model-b"]
        assert "skip-me" not in returned_attempts
        assert attempts == ["model-a", "model-b"]

    def test_all_unsupported_raises_exhausted(self) -> None:
        """Exhausting all models with no run raises the exhausted signal."""
        adapter = GenericCommandAdapter(command=["x"])
        adapter.supports_model = lambda m: False  # type: ignore[method-assign]

        def run_fn(model: str = "default") -> object:  # pragma: no cover - never called
            raise AssertionError("run_fn must not be called")

        with pytest.raises(ModelChainExhausted) as exc_info:
            try_fallback(adapter, ["a", "b"], "/tmp", None, run_fn)
        assert exc_info.value.attempts == []


class TestGenericAdapterNoDuplication:
    def test_configured_command_is_not_duplicated(self, tmp_path: Path) -> None:
        """Generic adapter's configured command is the complete command.

        The configured ``command`` is the entire invocation; the loop must
        not append ``agent_command[1:]`` on top, or every configured
        argument appears twice.
        """
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        cmd_log = tmp_path / "cmd.log"

        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            with open("{cmd_log}", "w") as f:
                f.write(repr(sys.argv[1:]) + "\\n")
            """,
        )

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
            adapter_config=AdapterConfig(
                name="generic", command=cmd + ["--flag", "value"]
            ),
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        run_loop(config)
        logged = cmd_log.read_text().strip()
        # ``--flag value`` must appear exactly once, not duplicated.
        assert logged.count("'--flag'") == 1
        assert logged.count("'value'") == 1
