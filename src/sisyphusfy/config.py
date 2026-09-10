"""Project configuration discovery, precedence, and defaults."""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

_PROJECT_CONFIG = ".sisyphusfy.toml"
_USER_CONFIG_DIR = ".config/sisyphusfy"
_USER_CONFIG_FILE = "config.toml"


class ConfigurationError(Exception):
    """Raised when project or user configuration cannot be parsed.

    The error message names the source file and the parse problem so the
    CLI can surface it instead of silently falling back to defaults.
    """


DEFAULT_CONFIG = {
    "adapter": "opencode",
    "model_chain": [],
    "workflow_type": "markdown",
    "agent_timeout": 60.0,
    "max_iterations": 10,
    "verification_command": [],
    "verification_timeout": 30.0,
    "handoff_path": "HANDOFF.md",
    "archive_enabled": False,
    "commit_enabled": False,
    "commit_allowed_files": [],
}


@dataclass
class SisyphusConfig:
    adapter: str = "opencode"
    model_chain: list[str] = field(default_factory=list)
    workflow_type: str = "markdown"
    agent_timeout: float = 60.0
    max_iterations: int = 10
    verification_command: list[str] = field(default_factory=list)
    verification_timeout: float = 30.0
    handoff_path: str = "HANDOFF.md"
    archive_enabled: bool = False
    commit_enabled: bool = False
    commit_allowed_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "adapter": self.adapter,
            "model_chain": self.model_chain,
            "workflow_type": self.workflow_type,
            "agent_timeout": self.agent_timeout,
            "max_iterations": self.max_iterations,
            "verification_command": self.verification_command,
            "verification_timeout": self.verification_timeout,
            "handoff_path": self.handoff_path,
            "archive_enabled": self.archive_enabled,
            "commit_enabled": self.commit_enabled,
            "commit_allowed_files": self.commit_allowed_files,
        }


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for k, v in override.items():
        if v is not None:
            merged[k] = v
    return merged


def _load_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)  # type: ignore[union-attr]
    except FileNotFoundError:
        return {}
    except PermissionError as exc:
        raise ConfigurationError(
            f"cannot read configuration file {path}: {exc}"
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(
            f"malformed TOML in {path}: {exc}"
        ) from exc


def _user_config_path() -> Path | None:
    home = Path.home()
    if home == Path("~"):
        return None
    return home / _USER_CONFIG_DIR / _USER_CONFIG_FILE


def load_config(project_dir: str = ".") -> SisyphusConfig:
    project_path = Path(project_dir).resolve()
    user_path = _user_config_path()

    user_data: dict = {}
    if user_path is not None:
        user_data = _load_toml(user_path)

    project_data = _load_toml(project_path / _PROJECT_CONFIG)

    merged = _merge(DEFAULT_CONFIG, user_data)
    merged = _merge(merged, project_data)

    return SisyphusConfig(
        adapter=merged["adapter"],
        model_chain=merged["model_chain"],
        workflow_type=merged["workflow_type"],
        agent_timeout=float(merged["agent_timeout"]),
        max_iterations=int(merged["max_iterations"]),
        verification_command=merged["verification_command"],
        verification_timeout=float(merged["verification_timeout"]),
        handoff_path=merged["handoff_path"],
        archive_enabled=bool(merged["archive_enabled"]),
        commit_enabled=bool(merged["commit_enabled"]),
        commit_allowed_files=merged["commit_allowed_files"],
    )


def apply_cli_overrides(config: SisyphusConfig, **overrides) -> SisyphusConfig:
    for k, v in overrides.items():
        if v is not None and hasattr(config, k):
            setattr(config, k, v)
    return config


def init_project_config(project_dir: str = ".", force: bool = False) -> Path:
    project_path = Path(project_dir).resolve()
    config_path = project_path / _PROJECT_CONFIG

    if config_path.exists() and not force:
        raise FileExistsError(
            f"configuration already exists: {config_path}\n"
            f"use --force to overwrite"
        )

    def _toml_value(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, list):
            if not v:
                return "[]"
            items = ", ".join(f'"{item}"' if isinstance(item, str) else str(item) for item in v)
            return f"[{items}]"
        if isinstance(v, str):
            return f'"{v}"'
        return repr(v)

    lines = [
        "# Sisyphusfy project configuration",
        "# Precedence: CLI flags > this file > user defaults > built-in defaults",
        "",
        f'adapter = {_toml_value(DEFAULT_CONFIG["adapter"])}',
        f"model_chain = {_toml_value(DEFAULT_CONFIG['model_chain'])}",
        f'workflow_type = {_toml_value(DEFAULT_CONFIG["workflow_type"])}',
        f"agent_timeout = {_toml_value(DEFAULT_CONFIG['agent_timeout'])}",
        f"max_iterations = {_toml_value(DEFAULT_CONFIG['max_iterations'])}",
        f"verification_command = {_toml_value(DEFAULT_CONFIG['verification_command'])}",
        f"verification_timeout = {_toml_value(DEFAULT_CONFIG['verification_timeout'])}",
        f'handoff_path = {_toml_value(DEFAULT_CONFIG["handoff_path"])}',
        f"archive_enabled = {_toml_value(DEFAULT_CONFIG['archive_enabled'])}",
        f"commit_enabled = {_toml_value(DEFAULT_CONFIG['commit_enabled'])}",
        f"commit_allowed_files = {_toml_value(DEFAULT_CONFIG['commit_allowed_files'])}",
        "",
    ]

    config_path.write_text("\n".join(lines))
    return config_path


def discover_task_path(project_dir: str = ".", change: str | None = None) -> str | None:
    project_path = Path(project_dir).resolve()

    if change:
        openspec_path = project_path / "openspec" / "changes" / change / "tasks.md"
        if openspec_path.exists():
            return str(openspec_path)

    for candidate in ["tasks.md", "TASKS.md", "task.md", "TASK.md"]:
        p = project_path / candidate
        if p.exists():
            return str(p)

    return None


def discover_handoff_path(project_dir: str = ".", config: SisyphusConfig | None = None) -> str | None:
    project_path = Path(project_dir).resolve()
    handoff = config.handoff_path if config else "HANDOFF.md"

    for name in [handoff, "HANDOFF.md", "handoff.md"]:
        p = project_path / name
        if p.exists():
            return str(p)

    return None


def discover_openspec_change(project_dir: str = ".", change: str | None = None) -> str | None:
    project_path = Path(project_dir).resolve()
    changes_dir = project_path / "openspec" / "changes"

    if not changes_dir.is_dir():
        return None

    if change:
        change_dir = changes_dir / change
        if change_dir.is_dir():
            tasks_file = change_dir / "tasks.md"
            if tasks_file.exists():
                return str(change_dir)
        return None

    for entry in sorted(changes_dir.iterdir()):
        if entry.is_dir():
            tasks_file = entry / "tasks.md"
            if tasks_file.exists():
                unchecked = 0
                for line in tasks_file.read_text().splitlines():
                    stripped = line.strip()
                    if stripped.startswith("- [ ]"):
                        unchecked += 1
                if unchecked > 0:
                    return str(entry)

    return None


class VerificationSource(str, Enum):
    """How a verification command was chosen."""

    CONFIGURED = "configured"
    DISCOVERED = "discovered"
    UNAVAILABLE = "unavailable"


class VerificationDetectionError(Exception):
    """A project marker exists but cannot be interpreted safely."""


@dataclass
class VerificationResolution:
    """A verification command and the reason it was chosen."""

    command: list[str] = field(default_factory=list)
    source: VerificationSource = VerificationSource.UNAVAILABLE
    detector: str = ""
    detail: str = ""

    @property
    def available(self) -> bool:
        return bool(self.command)

    def to_dict(self) -> dict:
        return {
            "command": list(self.command),
            "source": self.source.value,
            "detector": self.detector,
            "detail": self.detail,
            "available": self.available,
        }


_ExecutableCheck = Callable[[str], bool]
_Detector = Callable[[Path, _ExecutableCheck], list[str] | None]


def _detect_dotnet(project: Path, available: _ExecutableCheck) -> list[str] | None:
    if not available("dotnet"):
        return None
    solutions = sorted(p.name for p in project.glob("*.sln") if p.is_file())
    if solutions:
        return ["dotnet", "test", solutions[0]]
    projects = sorted(p.name for p in project.glob("*.csproj") if p.is_file())
    if projects:
        return ["dotnet", "test", projects[0]]
    return None


def _detect_rust(project: Path, available: _ExecutableCheck) -> list[str] | None:
    if available("cargo") and (project / "Cargo.toml").is_file():
        return ["cargo", "test"]
    return None


_PYTHON_MARKERS = ("pytest.ini", "pyproject.toml", "setup.cfg", "setup.py", "tox.ini")
_PYTHON_TEST_DIRS = ("tests", "test")


def _detect_python(project: Path, available: _ExecutableCheck) -> list[str] | None:
    if not available("pytest"):
        return None
    if any((project / marker).is_file() for marker in _PYTHON_MARKERS):
        return ["pytest"]
    if any((project / directory).is_dir() for directory in _PYTHON_TEST_DIRS):
        return ["pytest"]
    return None


def _detect_javascript(project: Path, available: _ExecutableCheck) -> list[str] | None:
    manifest = project / "package.json"
    if not manifest.is_file() or not available("npm"):
        return None
    try:
        data = json.loads(manifest.read_text(errors="replace"))
    except (OSError, ValueError) as exc:
        raise VerificationDetectionError(f"package.json could not be read: {exc}") from exc
    scripts = data.get("scripts") if isinstance(data, dict) else None
    test_script = scripts.get("test") if isinstance(scripts, dict) else None
    if isinstance(test_script, str) and test_script.strip():
        return ["npm", "test"]
    return None


def _detect_flutter(project: Path, available: _ExecutableCheck) -> list[str] | None:
    if available("flutter") and (project / "pubspec.yaml").is_file():
        return ["flutter", "test"]
    return None


_MAKEFILE_NAMES = ("Makefile", "makefile", "GNUmakefile")
_MAKE_TEST_TARGET = re.compile(r"^test\s*:", re.MULTILINE)


def _detect_make(project: Path, available: _ExecutableCheck) -> list[str] | None:
    """Select `make test` only when a Makefile declares a `test` target."""
    if not available("make"):
        return None
    for name in _MAKEFILE_NAMES:
        path = project / name
        if not path.is_file():
            continue
        try:
            content = path.read_text(errors="replace")
        except OSError as exc:
            raise VerificationDetectionError(f"{name} could not be read: {exc}") from exc
        if _MAKE_TEST_TARGET.search(content):
            return ["make", "test"]
    return None


# Ordered, deterministic precedence. The first detector whose project marker and
# executable are both present wins; later ecosystems are never reached.
DETECTORS: tuple[tuple[str, _Detector], ...] = (
    ("dotnet", _detect_dotnet),
    ("rust", _detect_rust),
    ("python", _detect_python),
    ("javascript", _detect_javascript),
    ("flutter", _detect_flutter),
    ("make", _detect_make),
)


def discover_verification_command(
    project_dir: str = ".",
    available: _ExecutableCheck | None = None,
) -> VerificationResolution:
    """Resolve a verification command from project markers.

    Detection is read-only: it inspects files and executable availability and
    never runs a candidate verifier.
    """
    project = Path(project_dir).resolve()
    executable_available = available or (lambda name: shutil.which(name) is not None)

    for name, detector in DETECTORS:
        try:
            command = detector(project, executable_available)
        except VerificationDetectionError as exc:
            # A marker exists but is unusable: stop instead of falling through
            # to an unrelated ecosystem command.
            return VerificationResolution(detector=name, detail=str(exc))
        if command:
            return VerificationResolution(
                command=command,
                source=VerificationSource.DISCOVERED,
                detector=name,
            )

    return VerificationResolution(detail="no supported project markers found")


def resolve_verification(
    configured: list[str] | None,
    project_dir: str = ".",
    available: _ExecutableCheck | None = None,
) -> VerificationResolution:
    """Prefer an explicit command, then marker-aware discovery."""
    if configured:
        return VerificationResolution(
            command=list(configured),
            source=VerificationSource.CONFIGURED,
        )
    return discover_verification_command(project_dir, available)


def find_verification_command(project_dir: str = ".") -> list[str] | None:
    """Return the discovered verification command, or None when there is none."""
    return discover_verification_command(project_dir).command or None
