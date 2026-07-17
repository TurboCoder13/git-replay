"""Tests for the standalone interactive HTML replay page renderer."""

from __future__ import annotations

from datetime import timezone
from pathlib import Path

import pytest
from assertpy import assert_that

from git_replay.model import Commit
from git_replay.render import page

_SNAPSHOT = Path(__file__).parent / "fixtures" / "page.html"

# Fixed, deterministic commit set backing the committed snapshot: three repos,
# three human authors plus one service bot, spanning several UTC days.
_SAMPLE: list[Commit] = [
    Commit(
        t=1_700_000_000,
        author="Ada",
        subject="Bootstrap core",
        repo="alpha",
        ins=120,
        dels=4,
    ),
    Commit(
        t=1_700_050_000,
        author="renovate[bot]",
        subject="Update deps",
        repo="alpha",
        ins=6,
        dels=6,
    ),
    Commit(
        t=1_700_120_000,
        author="Ada",
        subject="Add parser & </b> guard",
        repo="alpha",
        ins=88,
        dels=12,
    ),
    Commit(
        t=1_700_200_000, author="Lin", subject="Wire CLI", repo="beta", ins=64, dels=8
    ),
    Commit(
        t=1_700_260_000,
        author="Ada",
        subject="Refactor aggregate",
        repo="beta",
        ins=30,
        dels=40,
    ),
    Commit(
        t=1_700_330_000, author="Kai", subject="Docs pass", repo="gamma", ins=15, dels=2
    ),
    Commit(
        t=1_700_400_000,
        author="Lin",
        subject="Heatmap layout",
        repo="beta",
        ins=200,
        dels=18,
    ),
    Commit(
        t=1_700_460_000,
        author="renovate[bot]",
        subject="Bump pytest",
        repo="beta",
        ins=2,
        dels=2,
    ),
    Commit(
        t=1_700_540_000,
        author="Kai",
        subject="Fix off-by-one",
        repo="gamma",
        ins=3,
        dels=3,
    ),
    Commit(
        t=1_700_620_000,
        author="Ada",
        subject="Ship replay panel",
        repo="alpha",
        ins=310,
        dels=44,
    ),
]


def test_render_matches_snapshot() -> None:
    """The rendered page is byte-for-byte stable against the golden snapshot."""
    html = page.render(commits=_SAMPLE, tz=timezone.utc, org_label="demo-org")
    expected = _SNAPSHOT.read_text(encoding="utf-8")
    assert_that(html).is_equal_to(expected)


def test_render_is_self_contained() -> None:
    """The page inlines all CSS/JS and references no external resources."""
    html = page.render(commits=_SAMPLE, tz=timezone.utc)
    assert_that(html).starts_with("<!doctype html>")
    assert_that(html).contains("<style>").contains("<script>")
    # No external resource loads: no linked stylesheets, no sourced scripts or
    # images. (The SVG xmlns namespace URL is a declaration, not a fetch.)
    assert_that(html).does_not_contain("<link")
    assert_that(html).does_not_contain("src=")
    assert_that(html).does_not_contain('href="http')
    assert_that(html).does_not_contain("@import")


def test_render_carries_interactive_hooks() -> None:
    """The replay wiring (playhead, counters, observer, reduced-motion) is present."""
    html = page.render(commits=_SAMPLE, tz=timezone.utc)
    assert_that(html).contains("IntersectionObserver")
    assert_that(html).contains("prefers-reduced-motion")
    assert_that(html).contains("requestAnimationFrame")
    assert_that(html).contains('class="r-playhead"')
    assert_that(html).contains('class="rb"')
    assert_that(html).contains("threshold:0.35")


def test_render_uses_settled_agent_authored_framing() -> None:
    """The author panel keeps the settled agent-authored wording."""
    html = page.render(commits=_SAMPLE, tz=timezone.utc)
    assert_that(html).contains("agent-authored")
    assert_that(html).contains("authored by Claude Code")
    assert_that(html).does_not_contain("human-authored")


def test_render_neutralizes_closing_tags_in_baked_json() -> None:
    """A ``</`` sequence in baked data cannot terminate the script element."""
    html = page.render(commits=_SAMPLE, tz=timezone.utc)
    # The "</b>" subject reaches the JS ticker; "</" is rewritten to "<\/" so the
    # payload cannot close the enclosing <script> block early.
    assert_that(html).contains("<\\/b>")
    assert_that(html).does_not_contain('"alpha: Add parser & </b> guard"')


def test_render_embeds_the_heatmap_widget() -> None:
    """The heatmap panel embeds the reusable heatmap SVG renderer output."""
    html = page.render(commits=_SAMPLE, tz=timezone.utc)
    assert_that(html).contains('role="img"')
    assert_that(html).contains("Daily commit heatmap by year")


def test_render_stamps_the_last_commit_date() -> None:
    """The page footer carries a muted stamp of the max-commit (last) date."""
    html = page.render(commits=_SAMPLE, tz=timezone.utc)
    # Max commit t (1_700_620_000) resolves to Nov 22, 2023 in UTC.
    assert_that(html).contains('<footer class="stamp">data as of Nov 22, 2023</footer>')


def test_render_modules_do_not_use_wall_clock() -> None:
    """No renderer derives the stamp from wall-clock time, keeping output
    deterministic."""
    render_dir = Path(page.__file__).parent
    for module in sorted(render_dir.glob("*.py")):
        source = module.read_text(encoding="utf-8")
        assert_that(source).described_as(module.name).does_not_contain("datetime.now")
        assert_that(source).described_as(module.name).does_not_contain("time.time")


def test_render_rejects_empty_commits() -> None:
    """Rendering an empty history is a programming error."""
    with pytest.raises(ValueError):
        page.render(commits=[], tz=timezone.utc)
