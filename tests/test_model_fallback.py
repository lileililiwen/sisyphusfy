"""Test model fallback integration with the iteration loop."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.adapters import AdapterConfig
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


class TestModelChainFallback:
    def test_model_chain_fallback_on_quota(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys, os
            from pathlib import Path
            model = os.environ.get("AGENT_MODEL", "unknown")
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

    def test_all_models_exhausted(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys
            print("quota exceeded", file=sys.stderr)
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
        assert result.model_attempts == ["model-a", "model-b"]

    def test_adapter_error_unknown(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        config = LoopConfig(
            agent_command=["echo", "hi"],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            adapter_config=AdapterConfig(name="nonexistent"),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.ADAPTER_ERROR
        assert "unknown adapter" in result.adapter_error


class TestAdapterCommandConstruction:
    def test_generic_adapter_passes_command(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cwd_log = tmp_path / "cmd.txt"
        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import sys
            from pathlib import Path
            Path("{cwd_log}").write_text(" ".join(sys.argv[1:]))
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
            adapter_config=AdapterConfig(name="generic"),
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        logged_cmd = cwd_log.read_text()
        assert str(task_path) in logged_cmd


class TestModelChainWithAdapter:
    def test_model_chain_with_generic_adapter(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        cmd = _write_script(
            tmp_path,
            "agent.py",
            """\
            import sys, os
            from pathlib import Path
            model = os.environ.get("AGENT_MODEL", "")
            if model == "model-a":
                print("rate limit", file=sys.stderr)
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
            adapter_config=AdapterConfig(name="generic"),
            model_chain=["model-a", "model-b"],
            completion_strategy=MarkdownCheckboxCompletion(),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        assert "model-a" in result.model_attempts
        assert "model-b" in result.model_attempts
