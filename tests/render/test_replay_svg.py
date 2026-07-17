"""Tests for the animated replay-bars SVG renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from assertpy import assert_that

from git_replay.aggregate import Bucket, bucketize
from git_replay.model import Commit
from git_replay.render.replay_svg import ReplayMeta, render
from git_replay.render.theme import DARK, LIGHT


def _commit(
    t: int,
    ins: int,
    dels: int,
) -> Commit:
    """Build a fixture commit with the given timestamp and churn.

    Args:
        t: Commit timestamp in epoch seconds.
        ins: Insertions.
        dels: Deletions.

    Returns:
        A constructed :class:`Commit`.
    """
    return Commit(t=t, author="A", subject="s", repo="r", ins=ins, dels=dels)


def _fixture_buckets() -> list[Bucket]:
    """Bucketize a deterministic set of commits for the snapshot.

    The commits cover mostly-insertion, mostly-deletion, balanced, and
    zero-churn buckets so every fill branch is exercised.

    Returns:
        The bucketized fixture timeline.
    """
    commits = [
        _commit(t=1704067200, ins=120, dels=8),
        _commit(t=1704081600, ins=3, dels=64),
        _commit(t=1704240000, ins=40, dels=40),
        _commit(t=1704412800, ins=0, dels=0),
        _commit(t=1704585600, ins=200, dels=20),
        _commit(t=1704672000, ins=10, dels=90),
    ]
    buckets: list[Bucket] = bucketize(commits=commits, n_buckets=8)
    return buckets


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the directory holding snapshot fixtures.

    Returns:
        Path to ``tests/fixtures``.
    """
    return Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def replay_svg() -> str:
    """Render the widget for the fixture dataset.

    Returns:
        The rendered SVG string.
    """
    meta = ReplayMeta(
        first_label="Jan 1, 2024",
        last_label="Jan 8, 2024",
        span_days=7,
    )
    svg: str = render(buckets=_fixture_buckets(), meta=meta)
    return svg


def test_render_matches_snapshot(
    replay_svg: str,
    fixtures_dir: Path,
) -> None:
    """The full SVG output matches the committed snapshot byte for byte."""
    expected = (fixtures_dir / "replay_widget.svg").read_text(encoding="utf-8")
    assert_that(replay_svg).is_equal_to(expected)


def test_render_emits_one_bar_per_non_empty_bucket(
    replay_svg: str,
) -> None:
    """One ``<rect class="rb">`` is emitted per non-empty bucket."""
    non_empty = sum(1 for bucket in _fixture_buckets() if bucket.count)
    assert_that(replay_svg.count('<rect class="rb"')).is_equal_to(non_empty)


def test_render_declares_viewbox(
    replay_svg: str,
) -> None:
    """The SVG declares the taller 760x196 viewBox that fits the stamp."""
    assert_that(replay_svg).contains('viewBox="0 0 760 196"')


def test_render_stamps_the_last_commit_date(
    replay_svg: str,
) -> None:
    """The muted footer stamp reports the max-commit (last) date."""
    assert_that(replay_svg).contains("data as of Jan 8, 2024")


def test_render_embeds_style_block(
    replay_svg: str,
) -> None:
    """The animation lives in an embedded ``<style>`` block, not JavaScript."""
    assert_that(replay_svg).contains("<style>")
    assert_that(replay_svg).contains("@keyframes rb-sweep")
    assert_that(replay_svg).contains("@keyframes rb-reveal")
    assert_that(replay_svg).does_not_contain("<script")


def test_render_includes_reduced_motion_block(
    replay_svg: str,
) -> None:
    """A reduced-motion block disables animation and shows the final state."""
    assert_that(replay_svg).contains("@media (prefers-reduced-motion:reduce)")
    assert_that(replay_svg).contains(".rb{opacity:1;animation:none}")


def test_render_staggers_bar_animation_delays(
    replay_svg: str,
) -> None:
    """Bars carry proportional animation delays for the sweep reveal."""
    assert_that(replay_svg).contains("animation-delay:0.000s")
    assert_that(replay_svg).contains("animation-delay:22.500s")


def test_render_is_self_contained(
    replay_svg: str,
) -> None:
    """No external references are emitted, so the widget renders under camo."""
    assert_that(replay_svg).does_not_contain("http://www.w3.org/1999/xlink")
    assert_that(replay_svg).does_not_contain("<image")
    assert_that(replay_svg).does_not_contain("url(")


def test_render_lerps_fill_between_cyan_and_pink(
    replay_svg: str,
) -> None:
    """Mostly-insertion buckets skew pink; mostly-deletion buckets skew cyan."""
    assert_that(replay_svg).contains("rgb(225,123,187)")
    assert_that(replay_svg).contains("rgb(55,201,232)")
    assert_that(replay_svg).contains("rgb(60,66,80)")


def test_render_escapes_label_metacharacters() -> None:
    """XML metacharacters in labels are escaped in the output."""
    meta = ReplayMeta(
        first_label="A & B",
        last_label="<end>",
        span_days=1,
    )
    svg = render(buckets=_fixture_buckets(), meta=meta)
    assert_that(svg).contains("A &amp; B")
    assert_that(svg).contains("&lt;end&gt;")
    assert_that(svg).does_not_contain("<end>")


def test_render_light_uses_light_background_and_no_dark_background() -> None:
    """The light variant paints the white canvas and drops the dark background."""
    meta = ReplayMeta(first_label="Jan 1, 2024", last_label="Jan 8, 2024", span_days=7)
    dark = render(buckets=_fixture_buckets(), meta=meta, theme=DARK)
    svg = render(buckets=_fixture_buckets(), meta=meta, theme=LIGHT)
    assert_that(svg).contains(f'fill="{LIGHT.replay_background}"')
    assert_that(svg).does_not_contain(DARK.replay_background)
    # Re-theming the bar endpoints changes the interpolated fills.
    assert_that(svg).is_not_equal_to(dark)


def test_render_default_theme_is_dark() -> None:
    """Omitting the theme keeps the original dark background (zero drift)."""
    meta = ReplayMeta(first_label="Jan 1, 2024", last_label="Jan 8, 2024", span_days=7)
    svg = render(buckets=_fixture_buckets(), meta=meta)
    assert_that(svg).contains(f'fill="{DARK.replay_background}"')


def test_render_handles_empty_buckets() -> None:
    """An empty timeline still yields a valid, bar-free SVG."""
    meta = ReplayMeta(first_label="", last_label="", span_days=0)
    svg = render(buckets=[], meta=meta)
    assert_that(svg).contains("<svg")
    assert_that(svg).contains("</svg>")
    assert_that(svg).does_not_contain('<rect class="rb"')
