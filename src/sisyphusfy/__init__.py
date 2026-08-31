"""Sisyphusfy: project-agnostic supervisor for disposable AI-agent sessions."""

# Single source of truth for the release version. pyproject.toml reads it
# dynamically, and tests/test_version_sync.py enforces that every other
# artifact (npm manifest, npm launcher, installers) agrees with it.
__version__ = "0.1.0"
