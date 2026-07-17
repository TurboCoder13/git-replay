"""Tests for the incremental-fetch head-token manifest."""

from __future__ import annotations

from pathlib import Path

from assertpy import assert_that

from git_replay.manifest import MANIFEST_NAME, load_manifest, save_manifest


def test_manifest_round_trips(tmp_path: Path) -> None:
    """A saved manifest loads back into an equal mapping."""
    manifest = {
        "TurboCoder13/git-replay": "2026-01-05T00:00:00Z",
        "raycast/extensions": "2026-02-02T00:00:00Z",
    }

    save_manifest(tmp_path, manifest)

    assert_that(load_manifest(tmp_path)).is_equal_to(manifest)


def test_save_manifest_is_deterministic(tmp_path: Path) -> None:
    """Sorted-key serialization makes repeated saves byte-identical."""
    manifest = {"b/two": "2", "a/one": "1"}

    first = save_manifest(tmp_path, manifest).read_text(encoding="utf-8")
    second = save_manifest(tmp_path, manifest).read_text(encoding="utf-8")

    assert_that(first).is_equal_to(second)
    assert_that(first.index('"a/one"')).is_less_than(first.index('"b/two"'))


def test_load_manifest_missing_returns_empty(tmp_path: Path) -> None:
    """A directory without a manifest yields an empty mapping."""
    assert_that(load_manifest(tmp_path)).is_empty()


def test_load_manifest_malformed_returns_empty(tmp_path: Path) -> None:
    """Unparseable manifest content yields an empty mapping, not an error."""
    (tmp_path / MANIFEST_NAME).write_text("{not json", encoding="utf-8")

    assert_that(load_manifest(tmp_path)).is_empty()


def test_load_manifest_non_object_returns_empty(tmp_path: Path) -> None:
    """A JSON value that is not an object yields an empty mapping."""
    (tmp_path / MANIFEST_NAME).write_text('["a", "b"]', encoding="utf-8")

    assert_that(load_manifest(tmp_path)).is_empty()
