"""Tests for the daily heatmap SVG renderer."""

from __future__ import annotations

from datetime import date, timezone
from pathlib import Path

import pytest
from assertpy import assert_that

from git_replay.render.heatmap_svg import render
from git_replay.render.theme import DARK, LIGHT

_LEAP_COUNTS: dict[date, int] = {
    date(2012, 1, 1): 3,
    date(2012, 2, 29): 5,
    date(2012, 6, 15): 1,
    date(2012, 12, 31): 2,
}


# pytest.fixture reads as untyped under lintro's dependency-free mypy env
@pytest.fixture
def snapshot_dir() -> Path:
    """Return the directory holding rendered SVG snapshots.

    Returns:
        Path to ``tests/render/fixtures``.
    """
    return Path(__file__).parent / "fixtures"


def test_render_matches_leap_year_snapshot(snapshot_dir: Path) -> None:
    """The rendered leap-year heatmap matches its stored snapshot."""
    expected = (snapshot_dir / "heatmap_leap.svg").read_text(encoding="utf-8")
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc, data_as_of="Dec 31, 2012")
    assert_that(svg).is_equal_to(expected)


def test_render_light_uses_light_empty_cell_and_no_dark_empty() -> None:
    """The light variant fills empty cells with the light theme's empty colour."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc, theme=LIGHT)
    assert_that(svg).contains(f'fill="{LIGHT.heatmap_empty}"')
    assert_that(svg).does_not_contain(DARK.heatmap_empty)


def test_render_default_theme_is_dark() -> None:
    """Omitting the theme keeps the original dark empty-cell fill (zero drift)."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    assert_that(svg).contains(f'fill="{DARK.heatmap_empty}"')


def test_render_stamps_the_data_as_of_date() -> None:
    """A supplied ``data_as_of`` label renders as a muted footer stamp."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc, data_as_of="Dec 31, 2012")
    assert_that(svg).contains("data as of Dec 31, 2012")


def test_render_omits_stamp_without_data_as_of() -> None:
    """No stamp is rendered when ``data_as_of`` is omitted."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    assert_that(svg).does_not_contain("data as of")


def test_leap_year_renders_a_cell_per_day() -> None:
    """A leap year yields 366 day cells, each with a tooltip."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    assert_that(svg.count("<title>")).is_equal_to(366)


def test_non_leap_year_renders_a_cell_per_day() -> None:
    """A common year yields 365 day cells, each with a tooltip."""
    svg = render(daily_counts={date(2013, 3, 1): 1}, tz=timezone.utc)
    assert_that(svg.count("<title>")).is_equal_to(365)


def test_multiple_years_stack_their_cells() -> None:
    """Two years render both their day grids (365 + 365 cells)."""
    counts = {date(2013, 1, 1): 1, date(2014, 1, 1): 1}
    svg = render(daily_counts=counts, tz=timezone.utc)
    assert_that(svg.count("<title>")).is_equal_to(730)


def test_empty_days_use_the_empty_fill() -> None:
    """Days with no commits use the empty-cell colour, active days do not."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    # 366 days minus the 4 active days leaves 362 empty cells.
    assert_that(svg.count("#151923")).is_equal_to(362)


def test_active_days_use_the_plasma_ramp() -> None:
    """Active days and the four legend stops emit plasma ``rgb(...)`` colours."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    # 4 active cells + 4 legend gradient stops.
    assert_that(svg.count("rgb(")).is_equal_to(8)


def test_render_includes_a_legend_gradient() -> None:
    """The widget carries a legend running from one commit to the peak day."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    assert_that(svg).contains('fill="url(#hm-legend)"')
    assert_that(svg).contains("5 commits/day")


def test_render_surfaces_the_timezone_in_the_label() -> None:
    """The accessible label names the timezone the counts were bucketed in."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    assert_that(svg).contains("local days in UTC")


def test_render_stays_within_the_width_budget() -> None:
    """The widget stays within the ~700px width budget for READMEs."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    width = int(svg.split('width="', 1)[1].split('"', 1)[0])
    assert_that(width).is_less_than_or_equal_to(700)


def test_render_is_static_with_no_animation() -> None:
    """The output contains no animation elements."""
    svg = render(daily_counts=_LEAP_COUNTS, tz=timezone.utc)
    assert_that(svg).does_not_contain("<animate")
    assert_that(svg).does_not_contain("<script")


def test_render_empty_counts_returns_minimal_svg() -> None:
    """No data still yields a valid, labelled placeholder SVG."""
    svg = render(daily_counts={}, tz=timezone.utc)
    assert_that(svg).starts_with("<svg")
    assert_that(svg).contains("local days in UTC")
    assert_that(svg.count("<title>")).is_equal_to(0)
