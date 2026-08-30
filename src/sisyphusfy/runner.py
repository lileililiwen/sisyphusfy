from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from sisyphusfy.result import Classification, RunResult


def run_agent(
    command: list[str],
    *,
    working_directory: str | Path = ".",
    prompt: str | None = None,
    timeout: float = 60.0,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
) -> RunResult:
    cwd = str(Path(working_directory).resolve())

    if dry_run:
        return RunResult(
            command=command,
            exit_status=None,
            classification=Classification.DRY_RUN,
            working_directory=cwd,
            prompt=prompt,
            env=env or {},
        )

    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    stdin_data = (prompt + "\n").encode() if prompt else None

    start = time.monotonic()
    timed_out = False
    exit_status = -1
    stdout = ""
    stderr = ""

    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            input=stdin_data,
            capture_output=True,
            timeout=timeout,
            env=merged_env,
            check=False,
        )
        duration = (time.monotonic() - start) * 1000
        exit_status = proc.returncode
        stdout = proc.stdout.decode(errors="replace") if proc.stdout else ""
        stderr = proc.stderr.decode(errors="replace") if proc.stderr else ""
    except subprocess.TimeoutExpired as exc:
        duration = (time.monotonic() - start) * 1000
        timed_out = True
        stdout = exc.stdout.decode(errors="replace") if exc.stdout else ""
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""

    if timed_out:
        classification = Classification.TIMEOUT
    elif exit_status == 0:
        classification = Classification.SUCCESS
    else:
        classification = Classification.FAILURE

    return RunResult(
        command=command,
        exit_status=exit_status,
        classification=classification,
        stdout=stdout,
        stderr=stderr,
        duration_ms=round(duration, 2),
        timed_out=timed_out,
        working_directory=cwd,
        prompt=prompt,
        env=env or {},
    )
