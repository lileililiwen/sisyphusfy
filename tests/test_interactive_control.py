"""Tests for interactive loop controls: ESC pause and slash-command REPL."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.control import (
    ControlState,
    KeyWatcher,
    ReplContext,
    classify_key,
    dispatch_slash,
    feed_key,
    handle_prompt_text,
    parse_slash,
)
from sisyphusfy.loop import LoopConfig, LoopStopReason, PromptAnswer, run_loop


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


BLOCK_THEN_RESOLVE = '''\
import sys
prompt = sys.stdin.read()
if "Continue the task with that decision applied." in prompt:
    print("done")
    sys.exit(0)
print("NEED_PERMISSION: delete file", file=sys.stderr)
sys.exit(2)
'''

BLOCK_ALWAYS = '''\
import sys
print("NEED_PERMISSION: delete file", file=sys.stderr)
sys.exit(2)
'''


def _ctx(**overrides):  # type: ignore[no-untyped-def]
    said: list[str] = []
    params = {
        "model_chain": ["m1", "m2"],
        "default_model": "m1",
        "emit": said.append,
    }
    params.update(overrides)
    return ReplContext(**params), said  # type: ignore[arg-type]


class TestSlashParser:
    def test_commands_parse(self) -> None:
        assert parse_slash("/models") == ("/models", "")
        assert parse_slash("/models m2") == ("/models", "m2")
        assert parse_slash("  /compact  ") == ("/compact", "")
        assert parse_slash("plain answer") is None
        assert parse_slash("") is None

    def test_help_and_unknown_reprompt_without_forwarding(self) -> None:
        ctx, said = _ctx()
        state = ControlState()
        assert dispatch_slash("/help", "", ctx, state).action == "reprompt"
        assert dispatch_slash("/foo", "", ctx, state).action == "reprompt"
        assert any("/models" in line for line in said)

    def test_resume_and_stop(self) -> None:
        ctx, _ = _ctx()
        state = ControlState()
        assert dispatch_slash("/resume", "", ctx, state).action == "resume"
        assert dispatch_slash("/stop", "", ctx, state).action == "stop"

    def test_models_list_and_switch(self) -> None:
        ctx, said = _ctx()
        state = ControlState()
        assert dispatch_slash("/models", "", ctx, state).action == "reprompt"
        assert any("m1" in line and "m2" in line for line in said)
        out = dispatch_slash("/models", "m2", ctx, state)
        assert out.action == "reprompt"
        assert state.active_model == "m2"
        assert state.model_switches == ["m2"]

    def test_models_refuses_unsupported(self) -> None:
        ctx, said = _ctx(supports_model=lambda _m: False)
        state = ControlState()
        out = dispatch_slash("/models", "m9", ctx, state)
        assert out.action == "reprompt"
        assert state.active_model is None
        assert state.model_switches == []
        assert any("not supported" in line for line in said)

    def test_plain_text_is_answer_and_slash_never_forwards(self) -> None:
        ctx, _ = _ctx()
        state = ControlState()
        decision = handle_prompt_text("use staging", ctx, state)
        assert (decision.action, decision.text) == ("answer", "use staging")
        for slash in ("/models m2", "/compact", "/help", "/resume", "/stop", "/foo"):
            assert handle_prompt_text(slash, ctx, state).action != "answer"


class TestReplModelSwitch:
    def test_switch_changes_subsequent_invocation_and_records(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        seen_model = tmp_path / "model.txt"
        cmd = _write_script(
            tmp_path,
            "agent.py",
            f"""\
            import os, sys
            prompt = sys.stdin.read()
            if "Continue the task with that decision applied." in prompt:
                open({str(seen_model)!r}, "w").write(os.environ.get("AGENT_MODEL", ""))
                print("done")
                sys.exit(0)
            print("NEED_PERMISSION: delete file", file=sys.stderr)
            sys.exit(2)
            """,
        )
        script = iter(["/models m2", "go"])

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            prompt_user=lambda _b: PromptAnswer(
                denied=False, text=next(script)
            ),
        )
        result = run_loop(config)
        assert result.stop_reason != LoopStopReason.BLOCKED
        assert seen_model.read_text() == "m2"
        assert result.model_switches == ["m2"]
        assert result.to_dict()["model_switches"] == ["m2"]


class TestCompactCommand:
    def test_compact_reports_and_next_prompt_uses_compacted(
        self, tmp_path: Path
    ) -> None:
        from sisyphusfy.context import HandoffCompactor

        handoff = tmp_path / "HANDOFF.md"
        big = "y" * 10_000
        handoff.write_text(f"## Completed\n\n{big}\n\n## Next action\n\ncontinue\n")
        state = ControlState()
        said: list[str] = []
        ctx = ReplContext(
            handoff_path=str(handoff),
            on_compact=lambda: HandoffCompactor().compact(str(handoff)),
            emit=said.append,
        )
        out = dispatch_slash("/compact", "", ctx, state)
        assert out.action == "reprompt"
        assert any("->" in line for line in said)
        assert len(handoff.read_text()) < 10_000

    def test_compact_without_handoff_reports(self) -> None:
        ctx, said = _ctx(handoff_path=None)
        out = dispatch_slash("/compact", "", ctx, ControlState())
        assert out.action == "reprompt"
        assert any("nothing compacted" in line for line in said)


class TestEscPause:
    def test_lone_esc_pauses_but_csi_does_not(self) -> None:
        state = ControlState()
        assert classify_key(b"\x1b") == "esc"
        assert classify_key(b"\x1b[A") == "csi"
        assert classify_key(b"\x1bOP") == "csi"
        assert classify_key(b"a") == "other"
        assert feed_key(state, b"\x1b[A") is False
        assert state.pending_pause is False
        assert feed_key(state, b"\x1b") is True
        assert state.pending_pause is True

    def test_pending_pause_at_boundary_offers_resume(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        cmd = _write_script(tmp_path, "agent.py", "pass")
        control = ControlState(pending_pause=True)
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=1,
            interactive=True,
            prompt_user=lambda _b: PromptAnswer(denied=False, text="resume"),
            control_state=control,
        )
        result = run_loop(config)
        assert result.pause_count == 1
        assert result.to_dict()["pause_count"] == 1
        assert result.stop_reason != LoopStopReason.INTERRUPTED

    def test_pending_pause_at_boundary_stop_interrupts(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        cmd = _write_script(tmp_path, "agent.py", "pass")
        control = ControlState(pending_pause=True)
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            prompt_user=lambda _b: PromptAnswer(denied=False, text="stop"),
            control_state=control,
        )
        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.INTERRUPTED
        assert result.iterations == 0
        assert result.run_records == []
        assert result.pause_count == 1


class TestNonInteractive:
    def test_no_key_handling_without_tty(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        watcher = KeyWatcher(ControlState())
        assert watcher.start() is False
        assert watcher.active is False
        watcher.stop()

    def test_non_interactive_loop_never_prompts(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        cmd = _write_script(tmp_path, "agent.py", BLOCK_ALWAYS)

        def prompt_user(blocker: str) -> PromptAnswer:
            raise AssertionError("must not prompt when non-interactive")

        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=2,
            interactive=False,
            prompt_user=prompt_user,
        )
        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.BLOCKED
        assert result.pause_count == 0
        assert result.model_switches == []
        assert "pause_count" not in result.to_dict()
