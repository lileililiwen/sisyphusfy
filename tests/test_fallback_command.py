"""Test fallback captures every command and proves selected-model replacement."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.adapters import GenericCommandAdapter, ModelChainExhausted, try_fallback
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
        assert result.stop_reason == LoopStopReason.MODELS_EXHAUSTED
        env_content = env_log.read_text().strip().splitlines()
        assert env_content == ["model-a"]
