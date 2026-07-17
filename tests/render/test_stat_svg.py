"""Tests for the agent-authored stat-tile SVG renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from assertpy import assert_that

from git_replay.render.stat_svg import CAPTION, render

_SNAPSHOT = Path(__file__).parent / "fixtures" / "stat_tile.svg"


def test_render_matches_snapshot() -> None:
    """The rendered tile matches the committed golden SVG snapshot."""
    svg = render(
        agent_pct=94, agent_total=12345, bot_total=789, data_as_of="Jul 17, 2026"
    )
    expected = _SNAPSHOT.read_text(encoding="utf-8").rstrip("\n")
    assert_that(svg).is_equal_to(expected)


def test_render_stamps_the_data_as_of_date() -> None:
    """A supplied ``data_as_of`` label renders as a muted footer stamp and grows
    the tile to fit it."""
    svg = render(agent_pct=94, agent_total=1, bot_total=1, data_as_of="Jul 17, 2026")
    assert_that(svg).contains("data as of Jul 17, 2026")
    assert_that(svg).contains('viewBox="0 0 700 144"')


def test_render_omits_stamp_without_data_as_of() -> None:
    """No stamp is rendered when ``data_as_of`` is omitted."""
    svg = render(agent_pct=94, agent_total=1, bot_total=1)
    assert_that(svg).does_not_contain("data as of")


def test_render_is_self_contained_static_svg() -> None:
    """The output is a single SVG with no scripts or external references."""
    svg = render(agent_pct=50, agent_total=10, bot_total=10)
    assert_that(svg).starts_with("<svg").ends_with("</svg>")
    assert_that(svg).contains('viewBox="0 0 700 120"')
    assert_that(svg).does_not_contain("<script")
    assert_that(svg).does_not_contain("http://www.w3.org/1999/xlink")
    assert_that(svg).does_not_contain("<animate")


def test_render_uses_fixed_caption_verbatim() -> None:
    """The caption is emitted exactly as the settled product wording."""
    svg = render(agent_pct=94, agent_total=1, bot_total=1)
    assert_that(svg).contains(CAPTION)
    assert_that(CAPTION).is_equal_to(
        "authored by Claude Code under human direction · rest are service bots",
    )
    assert_that(svg).does_not_contain("typed by hand")
    assert_that(svg).does_not_contain("human-authored")


@pytest.mark.parametrize(
    ("agent_pct", "expected"),
    [
        (0, "0% agent-authored"),
        (7, "7% agent-authored"),
        (94, "94% agent-authored"),
        (100, "100% agent-authored"),
    ],
    ids=["pct=0", "pct=7", "pct=94", "pct=100"],
)
def test_render_formats_percentage(agent_pct: int, expected: str) -> None:
    """The headline reports the whole-number percentage, including 0 and 100."""
    svg = render(agent_pct=agent_pct, agent_total=1, bot_total=1)
    assert_that(svg).contains(f">{agent_pct}%</tspan>")
    assert_that(svg).contains(expected.split(" ", 1)[1])


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (0, "0"),
        (789, "789"),
        (1234, "1,234"),
        (12345, "12,345"),
        (1000000, "1,000,000"),
    ],
    ids=["zero", "no_separator", "one_separator", "two_groups", "millions"],
)
def test_render_thousands_separators(total: int, expected: str) -> None:
    """Commit totals render with grouped-thousands separators."""
    agent_svg = render(agent_pct=94, agent_total=total, bot_total=0)
    bot_svg = render(agent_pct=94, agent_total=0, bot_total=total)
    assert_that(agent_svg).contains(f">{expected}</text>")
    assert_that(bot_svg).contains(f">{expected}</text>")


def test_render_uses_monospace_tabular_figures() -> None:
    """Figures use a monospace stack with tabular numerals for alignment."""
    svg = render(agent_pct=94, agent_total=12345, bot_total=789)
    assert_that(svg).contains("ui-monospace, SFMono-Regular, Menlo, monospace")
    assert_that(svg).contains("font-variant-numeric:tabular-nums")


def test_render_carries_accessible_metadata() -> None:
    """The tile carries an accessible label and title for screen readers."""
    svg = render(agent_pct=94, agent_total=12345, bot_total=789)
    assert_that(svg).contains('role="img"')
    assert_that(svg).contains("aria-label=")
    assert_that(svg).contains("<title>").contains("</title>")
