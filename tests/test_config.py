"""Tests for TOML configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from assertpy import assert_that

from git_replay.config import Config, load_config

_TOML = """
owners = ["TurboCoder13", "lgtm-hq"]
exclude = ["ui-framework"]

[alias_map]
"Turbo Coder" = "TurboCoder13"
"Eitel" = "TurboCoder13"
"""


def test_load_config_parses_all_fields(tmp_path: Path) -> None:
    """A complete TOML file populates every Config field."""
    path = tmp_path / "config.toml"
    path.write_text(_TOML, encoding="utf-8")

    config = load_config(path)

    assert_that(config.owners).is_equal_to(["TurboCoder13", "lgtm-hq"])
    assert_that(config.exclude).is_equal_to(["ui-framework"])
    assert_that(config.alias_map).is_equal_to(
        {"Turbo Coder": "TurboCoder13", "Eitel": "TurboCoder13"},
    )


def test_load_config_defaults_missing_keys(tmp_path: Path) -> None:
    """Missing keys fall back to empty collections."""
    path = tmp_path / "config.toml"
    path.write_text('owners = ["solo"]\n', encoding="utf-8")

    config = load_config(path)

    assert_that(config.owners).is_equal_to(["solo"])
    assert_that(config.exclude).is_empty()
    assert_that(config.alias_map).is_empty()


def test_load_config_missing_file_raises(tmp_path: Path) -> None:
    """A non-existent path raises FileNotFoundError."""
    assert_that(load_config).raises(FileNotFoundError).when_called_with(
        tmp_path / "absent.toml",
    )


def test_load_config_rejects_wrong_list_type(tmp_path: Path) -> None:
    """A non-string list entry raises TypeError."""
    path = tmp_path / "config.toml"
    path.write_text("owners = [1, 2]\n", encoding="utf-8")

    with pytest.raises(TypeError):
        load_config(path)


def test_load_config_rejects_wrong_map_type(tmp_path: Path) -> None:
    """A non-string alias value raises TypeError."""
    path = tmp_path / "config.toml"
    path.write_text("[alias_map]\nname = 3\n", encoding="utf-8")

    with pytest.raises(TypeError):
        load_config(path)


def test_config_defaults_are_independent() -> None:
    """Default collections are not shared between instances."""
    first = Config()
    first.owners.append("x")

    assert_that(Config().owners).is_empty()
