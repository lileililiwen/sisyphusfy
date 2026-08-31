"""Tests for live progress, explicit timing, timeouts, and interruption."""

from __future__ import annotations

import io
import json
import os
import signal
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from sisyphusfy.hooks import HookConfig, HookType
from sisyphusfy.human import cmd_run
from sisyphusfy.loop import (
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    run_loop,
)
from sisyphusfy.progress import StreamProgress, format_duration
from sisyphusfy.result import Classification
from sisyphusfy.runner import run_agent

_POSIX = pytest.mark.skipif(
    sys.platform == "win32", reason="real interrupt delivery is POSIX-only"
)


def _script(tmp_path: Path, name: str, body: str) -> list[str]:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


def _agent_script(tmp_path: Path, *, extra: str = "") -> list[str]:
    """A fake agent that completes the task file and reports progress."""
    return _script(
        tmp_path,
        "agent.py",
        f"""\
        from pathlib import Path
        print("agent started", flush=True)
        Path("task.md").write_text("- [x] done\\n")
        {extra}
        """,
    )


def _loop_config(
    tmp_path: Path,
    task_path: Path,
    *,
    verification_command: list[str] | None = None,
    progress: StreamProgress | None = None,
    heartbeat_interval: float = 15.0,
    completion_hooks: list[HookConfig] | None = None,
    handoff_path: Path | None = None,
) -> LoopConfig:
    return LoopConfig(
        agent_command=_agent_script(tmp_path),
        working_directory=str(tmp_path),
        task_path=str(task_path),
        handoff_path=str(handoff_path) if handoff_path else None,
        prompt_template="do work",
        verification_command=verification_command,
        max_iterations=1,
        completion_strategy=MarkdownCheckboxCompletion(),
        completion_hooks=completion_hooks or [],
        progress=progress,
        heartbeat_interval=heartbeat_interval,
    )


def _human_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    verify_cmd: list[str],
    *extra_config: str,
) -> Path:
    """A project whose `generic` adapter completes the task file."""
    agent = tmp_path / "generic"
    agent.write_text(
        textwrap.dedent(f"""\
            #!{sys.executable}
            from pathlib import Path
            Path("tasks.md").write_text("- [x] done\\n")
            """)
    )
    agent.chmod(0o755)
    (tmp_path / "tasks.md").write_text("- [ ] work\n")
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    (tmp_path / ".sisyphusfy.toml").write_text(
        'adapter = "generic"\n'
        f"verification_command = {json.dumps(verify_cmd)}\n"
        + "".join(f"{line}\n" for line in extra_config)
    )
    return tmp_path


class TestDurationFormat:
    def test_zero(self) -> None:
        assert format_duration(0) == "0s"

    def test_under_a_minute(self) -> None:
        assert format_duration(42) == "42s"

    def test_over_a_minute(self) -> None:
        assert format_duration(72) == "1m 12s"

    def test_exactly_a_minute(self) -> None:
        assert format_duration(60) == "1m 0s"

    def test_fractional_seconds_truncate(self) -> None:
        assert format_duration(9.9) == "9s"

    def test_negative_becomes_zero(self) -> None:
        assert format_duration(-5) == "0s"

    def test_every_value_names_its_unit(self) -> None:
        for seconds in (0, 1, 42, 59, 60, 72, 600):
            assert format_duration(seconds).endswith("s")


class TestHeartbeatMessages:
    def test_line_is_labelled_with_its_component(self) -> None:
        stream = io.StringIO()
        StreamProgress(stream=stream).line("verify", "compiling")
        assert stream.getvalue() == "[verify] compiling\n"

    def test_heartbeat_reports_explicit_units(self) -> None:
        stream = io.StringIO()
        StreamProgress(stream=stream).heartbeat("verify", 72, 12)
        assert stream.getvalue() == "[verify] no output for 12s (elapsed 1m 12s)\n"

    def test_heartbeat_under_a_minute(self) -> None:
        stream = io.StringIO()
        StreamProgress(stream=stream).heartbeat("agent", 9, 3)
        assert stream.getvalue() == "[agent] no output for 3s (elapsed 9s)\n"


class TestStreamedLines:
    def test_stdout_lines_stream_as_they_arrive(self, tmp_path: Path) -> None:
        lines: list[str] = []
        cmd = _script(
            tmp_path,
            "chatty.py",
            """\
            import sys
            for index in range(3):
                print(f"line {index}", flush=True)
            """,
        )
        result = run_agent(cmd, working_directory=tmp_path, on_output=lines.append)
        assert result.exit_status == 0
        assert lines == ["line 0", "line 1", "line 2"]

    def test_stderr_lines_also_stream(self, tmp_path: Path) -> None:
        lines: list[str] = []
        cmd = _script(
            tmp_path,
            "noisy.py",
            """\
            import sys
            print("warning", file=sys.stderr, flush=True)
            """,
        )
        run_agent(cmd, working_directory=tmp_path, on_output=lines.append)
        assert "warning" in lines

    def test_blank_lines_are_not_reported(self, tmp_path: Path) -> None:
        lines: list[str] = []
        cmd = _script(
            tmp_path,
            "spaced.py",
            """\
            print("first")
            print()
            print("second")
            """,
        )
        run_agent(cmd, working_directory=tmp_path, on_output=lines.append)
        assert lines == ["first", "second"]

    def test_agent_and_verify_are_labelled(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        stream = io.StringIO()

        verify_cmd = _script(
            tmp_path,
            "verify.py",
            """\
            print("compiling", flush=True)
            """,
        )
        config = _loop_config(
            tmp_path,
            task_path,
            verification_command=verify_cmd,
            progress=StreamProgress(stream=stream),
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.COMPLETE
        output = stream.getvalue()
        assert "[agent] agent started" in output
        assert "[verify] compiling" in output


class TestIdleHeartbeats:
    def test_quiet_child_emits_heartbeats(self, tmp_path: Path) -> None:
        beats: list[tuple[float, float]] = []
        cmd = _script(tmp_path, "quiet.py", "import time; time.sleep(0.8)")
        run_agent(
            cmd,
            working_directory=tmp_path,
            timeout=10.0,
            on_heartbeat=lambda elapsed, idle: beats.append((elapsed, idle)),
            heartbeat_interval=0.15,
        )
        assert len(beats) >= 2
        assert all(idle >= 0.15 for _, idle in beats)
        assert beats[-1][0] > beats[0][0]

    def test_active_child_emits_no_heartbeat(self, tmp_path: Path) -> None:
        beats: list[tuple[float, float]] = []
        cmd = _script(
            tmp_path,
            "busy.py",
            """\
            import time
            for _ in range(14):
                print("working", flush=True)
                time.sleep(0.05)
            """,
        )
        run_agent(
            cmd,
            working_directory=tmp_path,
            timeout=10.0,
            on_heartbeat=lambda elapsed, idle: beats.append((elapsed, idle)),
            heartbeat_interval=0.5,
        )
        assert beats == []

    def test_quiet_verification_emits_a_heartbeat(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        stream = io.StringIO()

        verify_cmd = _script(tmp_path, "verify.py", "import time; time.sleep(0.8)")
        config = _loop_config(
            tmp_path,
            task_path,
            verification_command=verify_cmd,
            progress=StreamProgress(stream=stream),
            heartbeat_interval=0.15,
        )

        run_loop(config)
        assert "[verify] no output for" in stream.getvalue()


class TestBrokenProgressStream:
    def test_closed_stream_does_not_kill_the_child(self, tmp_path: Path) -> None:
        def broken(_text: str) -> None:
            raise BrokenPipeError("closed")

        cmd = _script(tmp_path, "ok.py", "print('finished')")
        result = run_agent(cmd, working_directory=tmp_path, on_output=broken)
        assert result.exit_status == 0
        assert result.classification == Classification.SUCCESS
        assert "finished" in result.stdout


class TestTimeoutReporting:
    def test_partial_output_is_kept_and_streamed(self, tmp_path: Path) -> None:
        lines: list[str] = []
        cmd = _script(
            tmp_path,
            "slow.py",
            """\
            import time
            print("compiling module 1", flush=True)
            time.sleep(30)
            """,
        )
        result = run_agent(
            cmd,
            working_directory=tmp_path,
            timeout=1.0,
            on_output=lines.append,
        )
        assert result.timed_out is True
        assert result.classification == Classification.TIMEOUT
        assert "compiling module 1" in result.stdout
        assert "compiling module 1" in lines

    def test_cli_reports_limit_output_and_log_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        verify_cmd = _script(
            tmp_path,
            "verify.py",
            """\
            import time
            print("compiling module 1", flush=True)
            time.sleep(30)
            """,
        )
        _human_project(tmp_path, monkeypatch, verify_cmd, "verification_timeout = 1.0")

        code = cmd_run(str(tmp_path))
        out = capsys.readouterr().out

        assert code == 1
        assert "verify timed out after 1s:" in out
        assert "compiling module 1" in out
        assert "resume with: sisyphusfy resume" in out

        log_lines = [
            line.strip().removeprefix("diagnostics: ")
            for line in out.splitlines()
            if line.strip().startswith("diagnostics: ")
        ]
        assert log_lines, f"no diagnostic log path reported:\n{out}"
        assert Path(log_lines[0]).exists()
        assert "compiling module 1" in Path(log_lines[0]).read_text()


class TestInterruption:
    @_POSIX
    def test_ctrl_c_classifies_a_running_child(self, tmp_path: Path) -> None:
        cmd = _script(
            tmp_path,
            "slow.py",
            """\
            import time
            print("started", flush=True)
            time.sleep(30)
            """,
        )
        timer = threading.Timer(0.4, lambda: os.kill(os.getpid(), signal.SIGINT))
        timer.start()
        try:
            result = run_agent(cmd, working_directory=tmp_path, timeout=30.0)
        finally:
            timer.cancel()

        assert result.interrupted is True
        assert result.timed_out is False
        assert result.classification == Classification.INTERRUPTED
        assert "started" in result.stdout

    def test_interruption_preserves_state_and_skips_hooks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        handoff_path = tmp_path / "HANDOFF.md"
        handoff_path.write_text("before\n")
        marker = tmp_path / "hook-ran"

        def interrupted_run(*_args, **_kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr("sisyphusfy.loop.run_agent", interrupted_run)

        hook_cmd = _script(
            tmp_path,
            "hook.py",
            f"""\
            from pathlib import Path
            Path({str(marker)!r}).write_text("ran")
            """,
        )
        config = _loop_config(
            tmp_path,
            task_path,
            handoff_path=handoff_path,
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.ARCHIVE,
                    command=hook_cmd,
                    working_directory=str(tmp_path),
                    enabled=True,
                )
            ],
        )

        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.INTERRUPTED
        assert result.completion_pipeline_result is None
        assert not marker.exists()
        assert task_path.read_text() == "- [ ] work\n"
        assert handoff_path.read_text() == "before\n"

    def test_interrupted_verification_stops_the_loop(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from sisyphusfy.result import RunResult

        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")

        def interrupted_run(*_args, **_kwargs):
            return RunResult(
                command=["verify"],
                exit_status=-1,
                classification=Classification.INTERRUPTED,
                interrupted=True,
            )

        monkeypatch.setattr("sisyphusfy.loop.run_agent", interrupted_run)

        config = _loop_config(tmp_path, task_path, verification_command=["verify"])
        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.INTERRUPTED

    @_POSIX
    def test_ctrl_c_during_an_agent_preserves_state(
        self,
        tmp_path: Path,
    ) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        handoff_path = tmp_path / "HANDOFF.md"
        handoff_path.write_text("before\n")
        marker = tmp_path / "hook-ran"

        agent_cmd = _script(
            tmp_path,
            "slow-agent.py",
            """\
            import time
            from pathlib import Path
            print("working", flush=True)
            Path("task.md").write_text("- [x] done\\n")
            time.sleep(30)
            """,
        )
        hook_cmd = _script(
            tmp_path,
            "hook.py",
            f"""\
            from pathlib import Path
            Path({str(marker)!r}).write_text("ran")
            """,
        )

        config = LoopConfig(
            agent_command=agent_cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            handoff_path=str(handoff_path),
            prompt_template="do work",
            max_iterations=1,
            completion_strategy=MarkdownCheckboxCompletion(),
            completion_hooks=[
                HookConfig(
                    hook_type=HookType.COMMIT,
                    command=hook_cmd,
                    working_directory=str(tmp_path),
                    enabled=True,
                )
            ],
        )

        timer = threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGINT))
        timer.start()
        try:
            result = run_loop(config)
        finally:
            timer.cancel()

        assert result.stop_reason == LoopStopReason.INTERRUPTED
        assert result.completion_pipeline_result is None
        assert not marker.exists()
        assert handoff_path.read_text() == "before\n"
        assert task_path.read_text() == "- [x] done\n"


class TestJsonStaysClean:
    def test_progress_never_reaches_json_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        verify_cmd = _script(
            tmp_path,
            "verify.py",
            """\
            print("compiling module 1", flush=True)
            """,
        )
        _human_project(tmp_path, monkeypatch, verify_cmd)

        cmd_run(str(tmp_path), json_output=True)
        captured = capsys.readouterr()

        data = json.loads(captured.out.strip())
        assert data["stop_reason"] == "complete"
        assert "[verify]" not in captured.out
        assert "[verify]" not in captured.err
        # The stream only appears as bounded structured evidence, never as progress.
        assert data["verification"]["stdout"] == "compiling module 1\n"

    def test_streaming_keeps_evidence_bounded(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        stream = io.StringIO()

        verify_cmd = _script(
            tmp_path,
            "verify.py",
            """\
            for _ in range(200):
                print("x" * 100, flush=True)
            """,
        )
        config = _loop_config(
            tmp_path,
            task_path,
            verification_command=verify_cmd,
            progress=StreamProgress(stream=stream),
        )

        result = run_loop(config)
        assert result.verification is not None
        assert result.verification.stdout_truncated is True
        assert len(result.verification.stdout) <= 2000
        # Progress still streamed every line even though evidence stays bounded.
        assert stream.getvalue().count("[verify] x") == 200
