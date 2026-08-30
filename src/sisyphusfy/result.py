from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Classification(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    DRY_RUN = "dry_run"


@dataclass
class RunResult:
    command: list[str]
    exit_status: int | None
    classification: Classification
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    timed_out: bool = False
    working_directory: str = ""
    prompt: str | None = None
    env: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_status": self.exit_status,
            "classification": self.classification.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
            "working_directory": self.working_directory,
            "prompt": self.prompt,
            "env": self.env,
        }
