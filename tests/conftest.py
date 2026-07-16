"""Shared fixtures for the git-replay test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


# pytest.fixture reads as untyped under lintro's dependency-free mypy env
@pytest.fixture  # type: ignore[untyped-decorator]
def logs_dir() -> Path:
    """Return the directory holding fixture git-log files.

    Returns:
        Path to ``tests/fixtures``.
    """
    return Path(__file__).parent / "fixtures"


# pytest.fixture reads as untyped under lintro's dependency-free mypy env
@pytest.fixture  # type: ignore[untyped-decorator]
def aliases() -> dict[str, str]:
    """Return an alias map collapsing two spellings onto one identity.

    Returns:
        Mapping of raw author name to canonical name.
    """
    return {
        "Turbo Coder": "TurboCoder13",
        "Eitel": "TurboCoder13",
    }
