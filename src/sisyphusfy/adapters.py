"""Agent adapter protocol, registry, and built-in implementations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class FailureClass(str, Enum):
    RETRYABLE_PROVIDER = "retryable_provider"
    RETRYABLE_PROCESS = "retryable_process"
    NON_RETRYABLE = "non_retryable"


@runtime_checkable
class AgentAdapter(Protocol):
    def build_command(
        self,
        working_directory: str,
        prompt: str | None = None,
    ) -> list[str]: ...

    def supports_model(self, model: str) -> bool: ...

    def classify_failure(
        self, exit_status: int, output: str
    ) -> FailureClass:
        """Map a finished process to a ``FailureClass``.

        ``output`` is the bounded combined stdout and stderr of the agent
        invocation. Both streams are concatenated before classification so
        an adapter sees a quota or rate-limit marker regardless of which
        stream the agent used. Adapters that still expect a single
        ``stderr`` argument are tolerated by the loop: a ``TypeError`` is
        caught and the failure is treated as non-retryable.
        """
        ...

    def parse_error(self, output: str) -> AgentError | None: ...

    def diagnostic_hint(self) -> str:
        """Return the command that diagnoses this agent CLI's failures."""
        ...


@dataclass
class AdapterConfig:
    name: str
    model: str | None = None
    command: list[str] = field(default_factory=list)


class AdapterError(Exception):
    pass


@dataclass
class AgentError:
    """A structured error recovered from an agent's own output.

    Agents differ in how they report failures, so every field is optional: the
    loop stops on the exit status whether or not an error can be parsed.
    """

    name: str | None = None
    message: str | None = None
    reference: str | None = None
    hint: str | None = None

    def to_dict(self) -> dict:
        d: dict = {}
        if self.name:
            d["name"] = self.name
        if self.message:
            d["message"] = self.message
        if self.reference:
            d["reference"] = self.reference
        if self.hint:
            d["hint"] = self.hint
        return d


def parse_error_envelope(output: str) -> AgentError | None:
    """Return the first JSON error envelope in combined agent output.

    Agents that report structured errors print an object, sometimes across
    several lines and sometimes on stdout, for example::

        Error: {"name": "UnknownError",
                "data": {"message": "Unexpected server error.", "ref": "err_abc"}}

    The scan tracks brace depth outside string literals and only decodes a
    balanced object that carries a ``name``, so ordinary agent output costs
    nothing and a malformed envelope never raises.
    """
    depth = 0
    start = 0
    in_string = False
    escaped = False

    for index, char in enumerate(output):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0:
                error = _error_from_json(output[start : index + 1])
                if error is not None:
                    return error

    return None


def _error_from_json(candidate: str) -> AgentError | None:
    """Decode one balanced object, or return None when it is not an error."""
    if '"name"' not in candidate:
        return None
    try:
        payload = json.loads(candidate)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None

    name = payload.get("name")
    if not isinstance(name, str) or not name:
        return None

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    message = data.get("message", payload.get("message"))
    reference = data.get("ref", data.get("reference", payload.get("ref")))
    return AgentError(
        name=name,
        message=message if isinstance(message, str) else None,
        reference=reference if isinstance(reference, str) else None,
    )


class ModelChainExhausted(Exception):
    def __init__(
        self,
        model_chain: list[str],
        attempts: list[str],
        last_result: object | None = None,
    ) -> None:
        self.model_chain = model_chain
        self.attempts = attempts
        self.last_result = last_result
        msg = f"all models exhausted: {', '.join(attempts)}"
        super().__init__(msg)


_RETRYABLE_PROVIDER_MARKERS = (
    "quota",
    "rate_limit",
    "rate limit",
    "429",
    "503",
    "502",
    "provider",
    "overloaded",
    "capacity",
)


def _classify_combined_output(exit_status: int, output: str) -> FailureClass:
    """Map an agent run to a ``FailureClass`` from its combined output.

    Provider-side retryable markers are scanned across the bounded combined
    stdout and stderr, so a marker on either stream classifies as
    ``RETRYABLE_PROVIDER``. Process-level signals (negative or >128 exit
    status) classify as ``RETRYABLE_PROCESS``. Anything else is a
    task-level non-retryable failure.
    """
    lower = (output or "").lower()
    for marker in _RETRYABLE_PROVIDER_MARKERS:
        if marker in lower:
            return FailureClass.RETRYABLE_PROVIDER
    if exit_status == -1 or exit_status > 128:
        return FailureClass.RETRYABLE_PROCESS
    return FailureClass.NON_RETRYABLE


def _combined_output(result: object) -> str:
    """Return the bounded combined stdout+stderr of an agent run.

    The combined output is the same view the loop uses to detect blocked
    markers and to recover structured error envelopes, so the fallback
    classifier sees the same evidence the rest of the loop saw.
    """
    stdout = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    if stdout and stderr:
        return f"{stdout}\n{stderr}"
    return stdout or stderr or ""


def _safe_classify_failure(
    adapter: AgentAdapter, exit_status: int, output: str
) -> FailureClass:
    """Call ``adapter.classify_failure`` defensively.

    A third-party adapter that still uses the old ``(exit_status, stderr)``
    signature raises ``TypeError`` when the loop passes the combined
    output. Treat the failure as non-retryable in that case so a stale
    custom adapter does not crash the loop or rotate models silently.
    """
    classify = getattr(adapter, "classify_failure", None)
    if classify is None:
        return FailureClass.NON_RETRYABLE
    try:
        return classify(exit_status, output)
    except TypeError:
        return FailureClass.NON_RETRYABLE
    except Exception:  # noqa: BLE001 - a custom adapter must not stop the loop
        return FailureClass.NON_RETRYABLE


class GenericCommandAdapter:
    def __init__(
        self,
        command: list[str],
        model: str | None = None,
    ) -> None:
        self.command = command
        self.model = model

    def build_command(
        self,
        working_directory: str,
        prompt: str | None = None,
    ) -> list[str]:
        return list(self.command)

    def supports_model(self, model: str) -> bool:
        return True

    def classify_failure(self, exit_status: int, output: str) -> FailureClass:
        return _classify_combined_output(exit_status, output)

    def parse_error(self, output: str) -> AgentError | None:
        return parse_error_envelope(output)

    def diagnostic_hint(self) -> str:
        cmd = " ".join(self.command)
        return (
            f"Run the agent directly to reproduce: {cmd} 'hi'\n"
            "Enable the agent CLI's own verbose/log flag and read its output."
        )


class OpenCodeAdapter:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def build_command(
        self,
        working_directory: str,
        prompt: str | None = None,
    ) -> list[str]:
        cmd = ["opencode", "run"]
        if self.model:
            cmd.extend(["--model", self.model])
        if prompt:
            cmd.append(prompt)
        return cmd

    def supports_model(self, model: str) -> bool:
        return True

    def classify_failure(self, exit_status: int, output: str) -> FailureClass:
        return _classify_combined_output(exit_status, output)

    def parse_error(self, output: str) -> AgentError | None:
        return parse_error_envelope(output)

    def diagnostic_hint(self) -> str:
        return "Run: opencode run 'hi' --print-logs --log-level DEBUG"


class CodeBuddyAdapter:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def build_command(
        self,
        working_directory: str,
        prompt: str | None = None,
    ) -> list[str]:
        cmd = ["codebuddy", "-p"]
        if self.model:
            cmd.extend(["--model", self.model])
        if prompt:
            cmd.append(prompt)
        return cmd

    def supports_model(self, model: str) -> bool:
        return True

    def classify_failure(self, exit_status: int, output: str) -> FailureClass:
        return _classify_combined_output(exit_status, output)

    def parse_error(self, output: str) -> AgentError | None:
        return parse_error_envelope(output)

    def diagnostic_hint(self) -> str:
        return (
            "Run: codebuddy 'hi' --verbose\n"
            "Check that the CodeBuddy CLI is authenticated and the configured model resolves."
        )


_BUILTIN_ADAPTERS: dict[str, type] = {
    "opencode": OpenCodeAdapter,
    "codebuddy": CodeBuddyAdapter,
    "generic": GenericCommandAdapter,
}


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, type] = dict(_BUILTIN_ADAPTERS)

    def register(self, name: str, adapter_cls: type) -> None:
        self._adapters[name] = adapter_cls

    def get(self, name: str) -> type | None:
        return self._adapters.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._adapters.keys())


def resolve_adapter(
    config: AdapterConfig,
    agent_command: list[str] | None = None,
    registry: AdapterRegistry | None = None,
) -> AgentAdapter:
    reg = registry or AdapterRegistry()
    cls = reg.get(config.name)
    if cls is None:
        raise AdapterError(
            f"unknown adapter: {config.name!r} "
            f"(available: {', '.join(reg.list_names())})"
        )
    if config.name == "generic":
        command = config.command if config.command else (agent_command or [])
        return GenericCommandAdapter(command=command, model=config.model)
    return cls(model=config.model)


def try_fallback(
    adapter: AgentAdapter,
    model_chain: list[str],
    working_directory: str,
    prompt: str | None,
    run_fn,
    *,
    max_retries: int = 0,
) -> tuple[object, list[str]]:
    attempts: list[str] = []
    result: object | None = None

    models = model_chain if model_chain else [adapter.model or "default"]

    for model in models:
        if not adapter.supports_model(model):
            continue
        attempts.append(model)
        result = run_fn(model=model)

        raw_exit = getattr(result, "exit_status", None)
        exit_status = raw_exit if raw_exit is not None else -1
        combined = _combined_output(result)
        classification = _safe_classify_failure(adapter, exit_status, combined)

        if exit_status == 0:
            return result, attempts
        if classification == FailureClass.NON_RETRYABLE:
            return result, attempts
        if classification == FailureClass.RETRYABLE_PROVIDER:
            continue
        if classification == FailureClass.RETRYABLE_PROCESS:
            continue
        return result, attempts

    raise ModelChainExhausted(
        model_chain=model_chain, attempts=attempts, last_result=result
    )
