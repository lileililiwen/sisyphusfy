"""Agent adapter protocol, registry, and built-in implementations."""

from __future__ import annotations

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

    def classify_failure(self, exit_status: int, stderr: str) -> FailureClass: ...


@dataclass
class AdapterConfig:
    name: str
    model: str | None = None
    command: list[str] = field(default_factory=list)


class AdapterError(Exception):
    pass


class ModelChainExhausted(Exception):
    def __init__(self, model_chain: list[str], attempts: list[str]) -> None:
        self.model_chain = model_chain
        self.attempts = attempts
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

    def classify_failure(self, exit_status: int, stderr: str) -> FailureClass:
        lower = stderr.lower()
        for marker in _RETRYABLE_PROVIDER_MARKERS:
            if marker in lower:
                return FailureClass.RETRYABLE_PROVIDER
        if exit_status == -1 or exit_status > 128:
            return FailureClass.RETRYABLE_PROCESS
        return FailureClass.NON_RETRYABLE


class OpenCodeAdapter:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def build_command(
        self,
        working_directory: str,
        prompt: str | None = None,
    ) -> list[str]:
        cmd = ["opencode", "--non-interactive"]
        if self.model:
            cmd.extend(["--model", self.model])
        return cmd

    def supports_model(self, model: str) -> bool:
        return True

    def classify_failure(self, exit_status: int, stderr: str) -> FailureClass:
        lower = stderr.lower()
        for marker in _RETRYABLE_PROVIDER_MARKERS:
            if marker in lower:
                return FailureClass.RETRYABLE_PROVIDER
        if exit_status == -1 or exit_status > 128:
            return FailureClass.RETRYABLE_PROCESS
        return FailureClass.NON_RETRYABLE


class CodeBuddyAdapter:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def build_command(
        self,
        working_directory: str,
        prompt: str | None = None,
    ) -> list[str]:
        cmd = ["codebuddy", "--non-interactive"]
        if self.model:
            cmd.extend(["--model", self.model])
        return cmd

    def supports_model(self, model: str) -> bool:
        return True

    def classify_failure(self, exit_status: int, stderr: str) -> FailureClass:
        lower = stderr.lower()
        for marker in _RETRYABLE_PROVIDER_MARKERS:
            if marker in lower:
                return FailureClass.RETRYABLE_PROVIDER
        if exit_status == -1 or exit_status > 128:
            return FailureClass.RETRYABLE_PROCESS
        return FailureClass.NON_RETRYABLE


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

    models = model_chain if model_chain else [adapter.model or "default"]

    for model in models:
        if not adapter.supports_model(model):
            continue
        attempts.append(model)
        result = run_fn(model=model)

        raw_exit = getattr(result, "exit_status", None)
        exit_status = raw_exit if raw_exit is not None else -1
        stderr = getattr(result, "stderr", "") or ""
        classification = adapter.classify_failure(exit_status, stderr)

        if exit_status == 0:
            return result, attempts
        if classification == FailureClass.NON_RETRYABLE:
            return result, attempts
        if classification == FailureClass.RETRYABLE_PROVIDER:
            continue
        if classification == FailureClass.RETRYABLE_PROCESS:
            continue
        return result, attempts

    raise ModelChainExhausted(model_chain=model_chain, attempts=attempts)
