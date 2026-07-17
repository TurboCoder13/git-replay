"""Tests for the shared renderer colour themes."""

from __future__ import annotations

import dataclasses

import pytest
from assertpy import assert_that

from git_replay.render.theme import DARK, LIGHT


def test_dark_theme_preserves_historical_colours() -> None:
    """The dark theme keeps the exact colours the widgets shipped with."""
    assert_that(DARK.surface).is_equal_to("#10131a")
    assert_that(DARK.border).is_equal_to("#1f2430")
    assert_that(DARK.replay_background).is_equal_to("#0d1017")
    assert_that(DARK.heatmap_empty).is_equal_to("#151923")
    assert_that(DARK.accent).is_equal_to("#f472b6")
    assert_that(DARK.zero_churn).is_equal_to("rgb(60,66,80)")
    assert_that(DARK.cyan).is_equal_to((34, 211, 238))
    assert_that(DARK.pink).is_equal_to((244, 114, 182))


def test_light_theme_uses_light_surfaces_and_dark_ink() -> None:
    """The light theme paints white/off-white surfaces with dark ink."""
    assert_that(LIGHT.surface).is_equal_to("#ffffff")
    assert_that(LIGHT.replay_background).is_equal_to("#ffffff")
    assert_that(LIGHT.track).is_equal_to("#f6f8fa")
    assert_that(LIGHT.headline).is_equal_to("#1f2328")
    assert_that(LIGHT.value).is_equal_to("#1f2328")


def test_light_theme_avoids_the_dark_surface_hexes() -> None:
    """No dark-surface hex leaks into the light theme's surface colours."""
    dark_surfaces = {
        DARK.surface,
        DARK.replay_background,
        DARK.heatmap_empty,
        DARK.track,
    }
    light_surfaces = {
        LIGHT.surface,
        LIGHT.replay_background,
        LIGHT.heatmap_empty,
        LIGHT.track,
    }
    assert_that(light_surfaces.intersection(dark_surfaces)).is_empty()


def test_themes_share_the_categorical_palette_order() -> None:
    """Both themes reuse the same load-bearing categorical palette order."""
    assert_that(LIGHT.categorical).is_equal_to(DARK.categorical)
    assert_that(DARK.categorical[0]).is_equal_to("#db2777")


def test_theme_is_frozen() -> None:
    """A theme is immutable once constructed."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        DARK.surface = "#000000"
