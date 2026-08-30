"""Test workflow state adapters: Markdown, JSON, external-command, OpenSpec."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from sisyphusfy.workflows import (
    ExternalCommandAdapter,
    JSONPredicateAdapter,
    MarkdownChecklistAdapter,
    OpenSpecAdapter,
    WorkflowConfig,
    WorkflowError,
    render_handoff_prompt,
)


def _write_script(tmp: Path, name: str, body: str) -> list[str]:
    path = tmp / name
    path.write_text(textwrap.dedent(body))
    path.chmod(0o755)
    return [sys.executable, str(path)]


class TestMarkdownChecklistAdapter:
    def test_checked_items_complete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] step 1\n- [x] step 2\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        assert adapter.is_complete() is True
        assert adapter.has_work() is False

    def test_unchecked_items_incomplete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] step 1\n- [ ] step 2\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        assert adapter.is_complete() is False
        assert adapter.has_work() is True

    def test_all_unchecked_incomplete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [ ] step 1\n- [ ] step 2\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        assert adapter.is_complete() is False
        assert adapter.has_work() is True

    def test_empty_file_complete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        assert adapter.is_complete() is True
        assert adapter.has_work() is False

    def test_no_checkboxes_complete(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("Just some text\nNo checkboxes here\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        assert adapter.is_complete() is True
        assert adapter.has_work() is False

    def test_malformed_checkboxes_ignored(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] valid\n- [] invalid\n- [  ] invalid\n- [X] uppercase\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        assert adapter.is_complete() is False
        assert adapter.has_work() is True

    def test_explain_returns_status(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] done\n- [ ] todo\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        explanation = adapter.explain()
        assert "1 unchecked" in explanation
        assert "1 checked" in explanation

    def test_snapshot_returns_content(self, tmp_path: Path) -> None:
        task_path = tmp_path / "task.md"
        task_path.write_text("- [x] step 1\n")
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        snap = adapter.snapshot()
        assert snap["task_path"] == "- [x] step 1\n"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        task_path = tmp_path / "nonexistent.md"
        adapter = MarkdownChecklistAdapter(task_path=str(task_path))
        with pytest.raises(WorkflowError, match="not found"):
            adapter.is_complete()


class TestJSONPredicateAdapter:
    def test_predicate_true_complete(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"done": True, "count": 5}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path),
            predicate="done",
        )
        assert adapter.is_complete() is True
        assert adapter.has_work() is False

    def test_predicate_false_incomplete(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"done": False}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path),
            predicate="done",
        )
        assert adapter.is_complete() is False
        assert adapter.has_work() is True

    def test_nested_predicate(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"status": {"phase": "complete"}}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path),
            predicate="status.phase",
        )
        assert adapter.is_complete() is True

    def test_comparison_predicate(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"count": 10}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path),
            predicate="count >= 10",
        )
        assert adapter.is_complete() is True

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text("not valid json {{{")
        adapter = JSONPredicateAdapter(
            state_path=str(state_path),
            predicate="done",
        )
        with pytest.raises(WorkflowError, match="invalid JSON"):
            adapter.is_complete()

    def test_missing_key_incomplete(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"other": "value"}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path),
            predicate="done",
        )
        assert adapter.is_complete() is False

    def test_explain_returns_status(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"done": False}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path),
            predicate="done",
        )
        explanation = adapter.explain()
        assert "done" in explanation
        assert "false" in explanation.lower()

    def test_snapshot_returns_content(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({"done": True}))
        adapter = JSONPredicateAdapter(
            state_path=str(state_path),
            predicate="done",
        )
        snap = adapter.snapshot()
        assert "done" in snap["state_path"]


class TestExternalCommandAdapter:
    def test_exit_zero_complete(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "check.py", "pass")
        adapter = ExternalCommandAdapter(check_command=cmd)
        assert adapter.is_complete() is True
        assert adapter.has_work() is False

    def test_exit_nonzero_incomplete(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "check.py", "import sys; sys.exit(1)")
        adapter = ExternalCommandAdapter(check_command=cmd)
        assert adapter.is_complete() is False
        assert adapter.has_work() is True

    def test_timeout_raises(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "slow.py", "import time; time.sleep(10)")
        adapter = ExternalCommandAdapter(check_command=cmd, timeout=0.1)
        with pytest.raises(WorkflowError, match="timed out"):
            adapter.is_complete()

    def test_command_not_found_raises(self, tmp_path: Path) -> None:
        adapter = ExternalCommandAdapter(check_command=["nonexistent-command-xyz"])
        with pytest.raises(WorkflowError, match="not found"):
            adapter.is_complete()

    def test_explain_returns_status(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "check.py", "import sys; sys.exit(42)")
        adapter = ExternalCommandAdapter(check_command=cmd)
        adapter.is_complete()
        explanation = adapter.explain()
        assert "42" in explanation

    def test_snapshot_returns_command(self, tmp_path: Path) -> None:
        cmd = _write_script(tmp_path, "check.py", "pass")
        adapter = ExternalCommandAdapter(check_command=cmd)
        snap = adapter.snapshot()
        assert "check.py" in snap["command"]


class TestOpenSpecAdapter:
    def test_all_tasks_checked_complete(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        tasks_file = change_dir / "tasks.md"
        tasks_file.write_text("- [x] task 1\n- [x] task 2\n")
        validation_cmd = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation_cmd,
        )
        assert adapter.is_complete() is True
        assert adapter.has_work() is False

    def test_unchecked_tasks_incomplete(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        tasks_file = change_dir / "tasks.md"
        tasks_file.write_text("- [x] task 1\n- [ ] task 2\n")
        validation_cmd = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation_cmd,
        )
        assert adapter.is_complete() is False
        assert adapter.has_work() is True

    def test_validation_failure_raises(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        tasks_file = change_dir / "tasks.md"
        tasks_file.write_text("- [x] task 1\n")
        validation_cmd = _write_script(tmp_path, "validate.py", "import sys; sys.exit(1)")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation_cmd,
        )
        with pytest.raises(WorkflowError, match="validation failed"):
            adapter.is_complete()

    def test_missing_tasks_file_raises(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        validation_cmd = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation_cmd,
        )
        with pytest.raises(WorkflowError, match="tasks.md not found"):
            adapter.is_complete()

    def test_explain_returns_status(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        tasks_file = change_dir / "tasks.md"
        tasks_file.write_text("- [x] done\n- [ ] todo\n")
        validation_cmd = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation_cmd,
        )
        adapter.is_complete()
        explanation = adapter.explain()
        assert "1 unchecked" in explanation

    def test_snapshot_returns_task_content(self, tmp_path: Path) -> None:
        change_dir = tmp_path / "change"
        change_dir.mkdir()
        tasks_file = change_dir / "tasks.md"
        tasks_file.write_text("- [x] task 1\n")
        validation_cmd = _write_script(tmp_path, "validate.py", "pass")
        adapter = OpenSpecAdapter(
            change_dir=str(change_dir),
            validation_command=validation_cmd,
        )
        snap = adapter.snapshot()
        assert "- [x] task 1" in snap["tasks"]


class TestWorkflowConfig:
    def test_config_from_dict(self) -> None:
        config = WorkflowConfig.from_dict({
            "type": "markdown",
            "task_path": "tasks.md",
        })
        assert config.adapter_type == "markdown"
        assert config.task_path == "tasks.md"

    def test_config_json_predicate(self) -> None:
        config = WorkflowConfig.from_dict({
            "type": "json",
            "state_path": "state.json",
            "predicate": "done",
        })
        assert config.adapter_type == "json"
        assert config.predicate == "done"

    def test_config_external_command(self) -> None:
        config = WorkflowConfig.from_dict({
            "type": "external",
            "check_command": ["./check.sh"],
        })
        assert config.adapter_type == "external"
        assert config.check_command == ["./check.sh"]

    def test_config_openspec(self) -> None:
        config = WorkflowConfig.from_dict({
            "type": "openspec",
            "change_dir": "openspec/changes/my-change",
            "validation_command": ["openspec", "validate"],
        })
        assert config.adapter_type == "openspec"
        assert config.change_dir == "openspec/changes/my-change"

    def test_config_unknown_type_raises(self) -> None:
        with pytest.raises(WorkflowError, match="unknown type"):
            WorkflowConfig.from_dict({"type": "unknown"})


class TestHandoffPrompt:
    def test_render_prompt_with_paths(self) -> None:
        template = "Continue working on {task_path}. Check {handoff_path} for context."
        result = render_handoff_prompt(
            template,
            task_path="/path/to/tasks.md",
            handoff_path="/path/to/handoff.md",
        )
        assert "/path/to/tasks.md" in result
        assert "/path/to/handoff.md" in result

    def test_render_prompt_without_handoff(self) -> None:
        template = "Continue working on {task_path}."
        result = render_handoff_prompt(template, task_path="/path/to/tasks.md")
        assert "/path/to/tasks.md" in result
        assert "{handoff_path}" not in result

    def test_render_prompt_no_transcript(self) -> None:
        template = "Tasks: {task_path}"
        result = render_handoff_prompt(
            template,
            task_path="/path/to/tasks.md",
            previous_conversation="this should not appear",
        )
        assert "this should not appear" not in result
