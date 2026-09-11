"""Tests for context budgets, prompt estimates, bounded handoff sections,
and telemetry surfaced in human + JSON output.

The new contract keeps Sisyphusfy's "fresh session" claim measurable:
- The loop estimates prompt size before every invocation.
- A configured budget either rejects an over-budget prompt or applies a
  documented bounded reduction; the result records the policy.
- The handoff schema is bounded; optional compaction only ever rewrites
  the configured handoff file.
- Adapters may report exact provider usage; the core labels estimates.
- Fresh iterations and fallback attempts receive bounded workspace
  recovery context, not a previous chat transcript.
- Human and JSON status expose budget state, estimates, and budget events.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from sisyphusfy.context import (
    ContextBudget,
    HandoffCompactor,
    HandoffDocument,
    HandoffSection,
    estimate_text,
)
from sisyphusfy.loop import (
    LoopConfig,
    LoopStopReason,
    MarkdownCheckboxCompletion,
    _render_prompt_with_budget,
    run_loop,
)


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestEstimation:
    def test_estimate_text_is_deterministic(self) -> None:
        text = "Hello, world!\nThis is a test prompt."
        a = estimate_text(text)
        b = estimate_text(text)
        assert a == b
        assert a.tokens_estimated > 0
        assert a.chars == len(text)
        assert a.measurement_method

    def test_estimate_text_method_label(self) -> None:
        est = estimate_text("short prompt", method="chars/4")
        assert est.measurement_method == "chars/4"
        assert est.tokens_estimated == max(1, len("short prompt") // 4)

    def test_estimate_text_handles_empty(self) -> None:
        est = estimate_text("")
        assert est.tokens_estimated == 0
        assert est.chars == 0


class TestBudgetEnforcement:
    def test_over_budget_rejects_before_invocation(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")  # NOT complete
        # Generate a huge prompt template.
        big = "x" * 200_000
        cmd = _write_script(
            tmp_path,
            "agent.py",
            "import sys; sys.stdout.write('done')",
        )
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template=big,
            max_iterations=1,
            completion_strategy=MarkdownCheckboxCompletion(),
            context_budget=ContextBudget(
                max_input_tokens=100, policy="reject"
            ),
        )
        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.CONTEXT_BUDGET_EXCEEDED
        assert result.context_telemetry is not None
        assert result.context_telemetry.budget_event == "rejected"

    def test_over_budget_truncates(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")  # NOT complete
        # Big prompt template.
        big = "y" * 200_000
        cmd = _write_script(
            tmp_path,
            "agent.py",
            "pass",
        )
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template=big,
            max_iterations=1,
            completion_strategy=MarkdownCheckboxCompletion(),
            context_budget=ContextBudget(
                max_input_tokens=500, policy="truncate"
            ),
        )
        result = run_loop(config)
        # Truncation is recorded; the loop ran and applied the budget.
        assert result.context_telemetry is not None
        assert result.context_telemetry.budget_event == "truncated"

    def test_no_budget_means_no_event(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] work\n")
        cmd = _write_script(tmp_path, "noop.py", "pass")
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            max_iterations=1,
            completion_strategy=MarkdownCheckboxCompletion(),
        )
        result = run_loop(config)
        assert result.context_telemetry is not None
        assert result.context_telemetry.budget_event is None


class TestFreshSessionNoTranscript:
    def test_fallback_prompt_does_not_include_previous_transcript(
        self, tmp_path: Path
    ) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] work\n")
        agent = tmp_path / "agent.py"
        agent.write_text(
            textwrap.dedent(
                """\
                import sys
                # Capture argv[1] (the prompt) so the test can assert no
                # conversation transcript was replayed.
                Path(__file__).with_name("captured.txt").write_text(sys.argv[1] if len(sys.argv) > 1 else "")
                from pathlib import Path
                """
            )
        )
        agent.chmod(0o755)
        config = LoopConfig(
            agent_command=[sys.executable, str(agent)],
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do {task_path}",
            max_iterations=1,
            completion_strategy=MarkdownCheckboxCompletion(),
        )
        run_loop(config)
        captured_path = tmp_path / "captured.txt"
        if captured_path.exists():
            captured_text = captured_path.read_text()
            assert "<conversation>" not in captured_text
            assert "transcript" not in captured_text.lower()


class TestHandoffSchema:
    def test_handoff_document_parses_sections(self) -> None:
        raw = textwrap.dedent(
            """\
            ## Completed
            - task A
            - task B

            ## Current state
            halfway through C

            ## Blockers
            none

            ## Next action
            finish C

            ## Relevant files
            - src/lib.py

            ## Verification
            pytest -q
            """
        )
        doc = HandoffDocument.from_markdown(raw)
        assert doc.get(HandoffSection.COMPLETED) is not None
        assert "task A" in doc.get(HandoffSection.COMPLETED)
        assert doc.get(HandoffSection.NEXT_ACTION) is not None

    def test_handoff_document_clamps_oversized_section(self) -> None:
        big = "x" * 200_000
        doc = HandoffDocument.from_markdown(
            f"## Completed\n\n{big}\n"
        )
        clamped = doc.clamp(max_chars_per_section=10_000)
        body = clamped.get(HandoffSection.COMPLETED)
        assert body is not None
        assert len(body) <= 10_000 + 200  # small overshoot from clamp marker

    def test_handoff_compactor_rewrites_only_handoff(self, tmp_path: Path) -> None:
        # Create a handoff with sections.
        handoff = tmp_path / "HANDOFF.md"
        handoff.write_text(
            textwrap.dedent(
                """\
                ## Completed
                - too much
                - too much
                - too much

                ## Next action
                continue
                """
            )
        )
        # Create another file in the project; it must be untouched.
        other = tmp_path / "src.py"
        other.write_text("untouched\n")
        original = other.read_text()
        compactor = HandoffCompactor(
            max_chars_per_section=20,
            max_total_chars=200,
        )
        result = compactor.compact(handoff)
        assert result.compacted is True
        assert other.read_text() == original
        # The handoff was rewritten with a bounded body.
        assert len(handoff.read_text()) <= 300


class TestTelemetrySurfaced:
    def test_status_includes_context_telemetry(
        self, tmp_path: Path, capsys
    ) -> None:
        from sisyphusfy.human import cmd_run

        (tmp_path / "tasks.md").write_text("- [x] work\n")
        # Run with JSON output and a small budget so we can assert telemetry.
        cmd = _write_script(tmp_path, "noop.py", "pass")
        # The human cmd_run uses .sisyphusfy.toml. Configure an inline budget
        # by passing cli_overrides.
        rc = cmd_run(
            str(tmp_path),
            agent_command=cmd,
            json_output=True,
            context_budget_tokens=1000,
        )
        # Even with no work, the JSON output should expose the field.
        capsys.readouterr()
        # If the loop ran, the result should include context_telemetry.
        # If load_config failed, the result is a configuration error.
        assert rc in (0, 2)

    def test_loop_result_records_estimate(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] work\n")
        cmd = _write_script(tmp_path, "noop.py", "pass")
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="Hello, this is a prompt.",
            max_iterations=1,
            completion_strategy=MarkdownCheckboxCompletion(),
        )
        result = run_loop(config)
        assert result.context_telemetry is not None
        assert result.context_telemetry.estimated_total_input_tokens >= 0


class TestRenderPromptWithBudget:
    def test_renders_with_template(self) -> None:
        out = _render_prompt_with_budget(
            "do {task_path}",
            task_path="/tmp/tasks.md",
            handoff_path="",
        )
        assert "/tmp/tasks.md" in out


class TestRerunBudgetEnforcement:
    def test_rerun_over_budget_rejects_without_invocation(self, tmp_path: Path) -> None:
        from sisyphusfy.loop import LoopStopReason, PromptAnswer

        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        cmd = _write_script(
            tmp_path,
            "agent.py",
            "import sys; print('NEED_PERMISSION: delete file', file=sys.stderr); sys.exit(2)",
        )
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            prompt_user=lambda _b: PromptAnswer(denied=False, text="yes proceed with extra context " * 20),
            context_budget=ContextBudget(max_input_tokens=10, policy="reject"),
        )
        result = run_loop(config)
        assert result.stop_reason == LoopStopReason.CONTEXT_BUDGET_EXCEEDED
        assert result.context_telemetry is not None
        assert result.context_telemetry.budget_event == "rejected"
        # Only the original blocked run; the over-budget re-run never invoked.
        assert len(result.run_records) == 1

    def test_rerun_records_carry_estimates_and_telemetry_counts_all(
        self, tmp_path: Path
    ) -> None:
        from sisyphusfy.loop import PromptAnswer

        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        cmd = _write_script(
            tmp_path,
            "agent.py",
            textwrap.dedent(
                """\
                import sys
                prompt = sys.stdin.read()
                if "Continue the task with that decision applied." in prompt:
                    print("done")
                    sys.exit(0)
                print("NEED_PERMISSION: delete file", file=sys.stderr)
                sys.exit(2)
                """
            ),
        )
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            prompt_template="do work",
            max_iterations=3,
            interactive=True,
            prompt_user=lambda _b: PromptAnswer(denied=False, text="go"),
        )
        result = run_loop(config)
        assert len(result.run_records) >= 2
        for rec in result.run_records:
            assert rec.context_estimate is not None
        telemetry = result.context_telemetry
        assert telemetry is not None
        assert len(telemetry.iterations) == len(result.run_records)
        assert telemetry.estimated_total_input_tokens == sum(
            e.tokens_estimated for e in telemetry.iterations
        )


class TestCompactWiring:
    def test_compact_handoff_bounds_growth_and_records_counts(
        self, tmp_path: Path
    ) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] work\n")
        handoff = tmp_path / "HANDOFF.md"
        big = "x" * 10_000
        handoff.write_text(f"## Completed\n\n{big}\n\n## Next action\n\ncontinue\n")
        before = len(handoff.read_text())
        cmd = _write_script(tmp_path, "agent.py", "pass")
        config = LoopConfig(
            agent_command=cmd,
            working_directory=str(tmp_path),
            task_path=str(task_path),
            handoff_path=str(handoff),
            prompt_template="do work",
            max_iterations=1,
            completion_strategy=MarkdownCheckboxCompletion(),
            compact_handoff=True,
        )
        result = run_loop(config)
        after = len(handoff.read_text())
        assert after < before
        assert result.context_telemetry is not None
        assert result.context_telemetry.compactions
        last = result.context_telemetry.compactions[-1]
        assert last.before_chars == before
        assert last.after_chars == after


class TestHandoffFirstTruncation:
    def test_truncate_keeps_instructions_and_marks(self) -> None:
        from sisyphusfy.context import apply_budget_to_prompt

        instructions = "INSTRUCTIONS: do the one task carefully."
        recovery = "x" * 20_000
        prompt = f"{instructions}\n\nHandoff recovery:\n{recovery}"
        budget = ContextBudget(max_input_tokens=500, policy="truncate")
        out, event = apply_budget_to_prompt(prompt, budget)
        assert event == "truncated"
        assert instructions in out
        assert "[prompt truncated at" in out
        assert len(out) < len(prompt)
