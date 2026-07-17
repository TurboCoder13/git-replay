"""TOML-backed configuration for git-replay fetching."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """User configuration controlling which repositories are fetched.

    Attributes:
        owners: GitHub logins whose public repositories are discovered.
        exclude: Repository names skipped during discovery.
        alias_map: Mapping of author display names to a canonical identity.
        label: Human-readable identity shown on the rendered page.
    """

    owners: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    alias_map: dict[str, str] = field(default_factory=dict)
    label: str = "TurboCoder13"


def load_config(path: str | Path) -> Config:
    """Load a :class:`Config` from a TOML file.

    Args:
        path: Filesystem path to the TOML configuration file.

    Returns:
        The parsed configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        TypeError: If a configuration key holds a value of the wrong type.
    """
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    owners = _as_str_list(value=data.get("owners", []), key="owners")
    exclude = _as_str_list(value=data.get("exclude", []), key="exclude")
    alias_map = _as_str_map(value=data.get("alias_map", {}), key="alias_map")
    label = data.get("label", "TurboCoder13")
    if not isinstance(label, str):
        raise TypeError("'label' must be a string")
    return Config(owners=owners, exclude=exclude, alias_map=alias_map, label=label)


def _as_str_list(value: object, key: str) -> list[str]:
    """Coerce a TOML value into a list of strings.

    Args:
        value: The raw value read from the TOML document.
        key: The configuration key, used for error messages.

    Returns:
        The value as a list of strings.

    Raises:
        TypeError: If ``value`` is not a list of strings.
    """
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise TypeError(f"'{key}' must be a list of strings")
    return list(value)


def _as_str_map(value: object, key: str) -> dict[str, str]:
    """Coerce a TOML value into a mapping of strings to strings.

    Args:
        value: The raw value read from the TOML document.
        key: The configuration key, used for error messages.

    Returns:
        The value as a ``dict[str, str]``.

    Raises:
        TypeError: If ``value`` is not a mapping of strings to strings.
    """
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise TypeError(f"'{key}' must be a table of string values")
    return dict(value)
