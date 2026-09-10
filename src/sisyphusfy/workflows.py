"""Workflow state adapters for task progress tracking."""

from __future__ import annotations

import json
import operator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from sisyphusfy.diagnostics import subprocess_log_dir
from sisyphusfy.result import Classification
from sisyphusfy.runner import run_command


class WorkflowError(Exception):
    pass


@runtime_checkable
class WorkflowAdapter(Protocol):
    def has_work(self) -> bool: ...
    def is_complete(self) -> bool: ...
    def explain(self) -> str: ...
    def snapshot(self) -> dict[str, str]: ...
    def reload(self) -> None: ...


@dataclass
class WorkflowConfig:
    adapter_type: str
    task_path: str = ""
    state_path: str = ""
    predicate: str = ""
    check_command: list[str] = field(default_factory=list)
    change_dir: str = ""
    validation_command: list[str] = field(default_factory=list)
    timeout: float = 30.0
    working_directory: str = ""
    dry_run: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> WorkflowConfig:
        adapter_type = data.get("type", "")
        valid_types = {"markdown", "json", "external", "openspec"}
        if adapter_type not in valid_types:
            raise WorkflowError(f"unknown type: {adapter_type!r} (valid: {', '.join(sorted(valid_types))})")
        return cls(
            adapter_type=adapter_type,
            task_path=data.get("task_path", ""),
            state_path=data.get("state_path", ""),
            predicate=data.get("predicate", ""),
            check_command=data.get("check_command", []),
            change_dir=data.get("change_dir", ""),
            validation_command=data.get("validation_command", []),
            timeout=data.get("timeout", 30.0),
            working_directory=data.get("working_directory", ""),
            dry_run=bool(data.get("dry_run", False)),
        )


class MarkdownChecklistAdapter:
    def __init__(self, task_path: str) -> None:
        self._task_path = task_path
        self._path = Path(task_path)
        self._content: str | None = None

    def _ensure_loaded(self) -> None:
        if self._content is None:
            if not self._path.exists():
                raise WorkflowError(f"task file not found: {self._task_path}")
            self._content = self._path.read_text()

    def _parse_checkboxes(self) -> tuple[int, int]:
        self._ensure_loaded()
        checked = 0
        unchecked = 0
        for line in self._content.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- [x]", "- [X]")):
                checked += 1
            elif stripped.startswith("- [") and "]" in stripped[3:]:
                unchecked += 1
        return checked, unchecked

    def has_work(self) -> bool:
        _, unchecked = self._parse_checkboxes()
        return unchecked > 0

    def is_complete(self) -> bool:
        return not self.has_work()

    def explain(self) -> str:
        checked, unchecked = self._parse_checkboxes()
        parts = []
        if unchecked > 0:
            parts.append(f"{unchecked} unchecked")
        if checked > 0:
            parts.append(f"{checked} checked")
        return ", ".join(parts) if parts else "no checkboxes found"

    def snapshot(self) -> dict[str, str]:
        self._ensure_loaded()
        return {"task_path": self._content}

    def reload(self) -> None:
        self._content = None


class JSONPredicateAdapter:
    def __init__(self, state_path: str, predicate: str) -> None:
        self._state_path = state_path
        self._predicate = predicate
        self._path = Path(state_path)
        self._data: dict | None = None

    def _ensure_loaded(self) -> None:
        if self._data is None:
            if not self._path.exists():
                self._data = {}
                return
            try:
                self._data = json.loads(self._path.read_text())
            except json.JSONDecodeError as exc:
                raise WorkflowError(f"invalid JSON in {self._state_path}: {exc}") from exc

    def _resolve_predicate(self) -> bool:
        self._ensure_loaded()
        if self._data is None:
            return False

        parts = self._predicate.split()
        if len(parts) == 3 and parts[1] in (">=", "<=", "==", "!=", ">", "<"):
            key, op_str, value_str = parts
            current = self._get_nested_value(key)
            if current is None:
                return False
            op_func = getattr(operator, {
                ">=": "ge", "<=": "le", "==": "eq", "!=": "ne", ">": "gt", "<": "lt"
            }[op_str])
            try:
                if isinstance(current, bool):
                    return op_func(current, value_str.lower() == "true")
                return op_func(current, type(current)(value_str))
            except (ValueError, TypeError):
                return False
        else:
            value = self._get_nested_value(self._predicate)
            if isinstance(value, bool):
                return value
            return bool(value)

    def _get_nested_value(self, key: str) -> object:
        current = self._data
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def has_work(self) -> bool:
        return not self.is_complete()

    def is_complete(self) -> bool:
        return self._resolve_predicate()

    def explain(self) -> str:
        self._ensure_loaded()
        value = self._get_nested_value(self._predicate.split()[0] if " " in self._predicate else self._predicate)
        return f"{self._predicate} is {json.dumps(value)}"

    def snapshot(self) -> dict[str, str]:
        self._ensure_loaded()
        return {"state_path": json.dumps(self._data, indent=2)}

    def reload(self) -> None:
        self._data = None


class ExternalCommandAdapter:
    def __init__(
        self,
        check_command: list[str],
        timeout: float = 30.0,
        working_directory: str = ".",
        dry_run: bool = False,
    ) -> None:
        self._check_command = check_command
        self._timeout = timeout
        self._working_directory = working_directory
        self._dry_run = dry_run
        self._last_returncode: int | None = None

    @property
    def check_command(self) -> list[str]:
        return self._check_command

    def has_work(self) -> bool:
        return not self.is_complete()

    def is_complete(self) -> bool:
        if self._dry_run:
            return False
        result = run_command(
            self._check_command,
            working_directory=self._working_directory,
            component="workflow",
            timeout=self._timeout,
            log_dir=subprocess_log_dir(self._working_directory),
        )
        self._last_returncode = result.exit_status
        classification = result.classification
        if classification == Classification.COMMAND_NOT_FOUND:
            raise WorkflowError(
                f"command not found: {self._check_command[0]}"
            )
        if classification == Classification.TIMEOUT:
            raise WorkflowError(f"command timed out after {self._timeout}s")
        if classification == Classification.INTERRUPTED:
            raise WorkflowError("command interrupted")
        return result.exit_status is None or result.exit_status == 0

    def explain(self) -> str:
        if self._last_returncode is None:
            return "command not yet run"
        return f"exit code {self._last_returncode}"

    def snapshot(self) -> dict[str, str]:
        return {"command": " ".join(self._check_command)}

    def reload(self) -> None:
        self._last_returncode = None


class OpenSpecAdapter:
    def __init__(
        self,
        change_dir: str,
        validation_command: list[str],
        timeout: float = 30.0,
        working_directory: str = ".",
        dry_run: bool = False,
    ) -> None:
        self._change_dir = Path(change_dir)
        self._validation_command = validation_command
        self._timeout = timeout
        self._working_directory = working_directory
        self._dry_run = dry_run
        self._tasks_content: str | None = None

    def _ensure_tasks_loaded(self) -> None:
        if self._tasks_content is None:
            tasks_file = self._change_dir / "tasks.md"
            if not tasks_file.exists():
                raise WorkflowError(f"tasks.md not found in {self._change_dir}")
            self._tasks_content = tasks_file.read_text()

    def _parse_tasks(self) -> tuple[int, int]:
        self._ensure_tasks_loaded()
        checked = 0
        unchecked = 0
        for line in self._tasks_content.splitlines():
            stripped = line.strip()
            if stripped.startswith("- [x]"):
                checked += 1
            elif stripped.startswith("- [ ]"):
                unchecked += 1
        return checked, unchecked

    @property
    def validation_command(self) -> list[str]:
        return self._validation_command

    def _run_validation(self) -> None:
        result = run_command(
            self._validation_command,
            working_directory=self._working_directory,
            component="workflow",
            timeout=self._timeout,
            log_dir=subprocess_log_dir(self._working_directory),
        )
        classification = result.classification
        if classification == Classification.COMMAND_NOT_FOUND:
            raise WorkflowError(
                f"validation command not found: {self._validation_command[0]}"
            )
        if classification == Classification.TIMEOUT:
            raise WorkflowError(f"validation timed out after {self._timeout}s")
        if classification == Classification.INTERRUPTED:
            raise WorkflowError("validation interrupted")
        if result.exit_status != 0:
            raise WorkflowError(
                f"validation failed with exit code {result.exit_status}"
            )

    def has_work(self) -> bool:
        return not self.is_complete()

    def is_complete(self) -> bool:
        _, unchecked = self._parse_tasks()
        if unchecked > 0:
            return False
        if self._dry_run or not self._validation_command:
            return True
        self._run_validation()
        return True

    def explain(self) -> str:
        checked, unchecked = self._parse_tasks()
        parts = []
        if unchecked > 0:
            parts.append(f"{unchecked} unchecked")
        if checked > 0:
            parts.append(f"{checked} checked")
        return ", ".join(parts) if parts else "no tasks found"

    def snapshot(self) -> dict[str, str]:
        self._ensure_tasks_loaded()
        return {"tasks": self._tasks_content}

    def reload(self) -> None:
        self._tasks_content = None


def render_handoff_prompt(
    template: str,
    task_path: str = "",
    handoff_path: str = "",
    previous_conversation: str = "",
) -> str:
    try:
        result = template.format(task_path=task_path, handoff_path=handoff_path)
    except KeyError:
        result = template
    return result


def adapter_runs_commands(adapter: WorkflowAdapter) -> bool:
    """Report whether completing evaluation would execute a subprocess.

    Custom adapters can declare a ``runs_commands`` attribute instead of being
    one of the built-in command-driven adapters.
    """
    if isinstance(adapter, ExternalCommandAdapter):
        return bool(adapter.check_command)
    if isinstance(adapter, OpenSpecAdapter):
        return bool(adapter.validation_command)
    return bool(getattr(adapter, "runs_commands", False))


def resolve_workflow_adapter(config: WorkflowConfig) -> WorkflowAdapter:
    if config.adapter_type == "markdown":
        return MarkdownChecklistAdapter(task_path=config.task_path)
    elif config.adapter_type == "json":
        return JSONPredicateAdapter(state_path=config.state_path, predicate=config.predicate)
    elif config.adapter_type == "external":
        return ExternalCommandAdapter(
            check_command=config.check_command,
            timeout=config.timeout,
            working_directory=config.working_directory or ".",
            dry_run=config.dry_run,
        )
    elif config.adapter_type == "openspec":
        return OpenSpecAdapter(
            change_dir=config.change_dir,
            validation_command=config.validation_command,
            timeout=config.timeout,
            working_directory=config.working_directory or ".",
            dry_run=config.dry_run,
        )
    else:
        raise WorkflowError(f"unknown adapter type: {config.adapter_type!r}")
