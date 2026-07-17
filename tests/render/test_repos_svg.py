"""Tests for the compact per-repo bars SVG renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from assertpy import assert_that

from git_replay.render.repos_svg import _FOLD_COLOR, _PALETTE, render
from git_replay.render.theme import DARK, LIGHT

_SNAPSHOT = Path(__file__).parent / "fixtures" / "repos_svg.svg"
_SNAPSHOT_PINNED = Path(__file__).parent / "fixtures" / "repos_svg_pinned.svg"

# Fixed input backing the committed snapshot (11 repos -> 8 bars + fold).
_SAMPLE: dict[str, int] = {
    "git-replay": 128,
    "turbo-themes": 96,
    "py-lintro": 74,
    "raycast-extensions": 63,
    "dotfiles": 41,
    "scratch-notes": 38,
    "infra-pipeline-orchestrator-service": 27,
    "blog": 19,
    "gists": 12,
    "sandbox": 7,
    "archive-old": 3,
}


def test_render_matches_snapshot() -> None:
    """The renderer output is byte-for-byte stable against the snapshot."""
    expected = _SNAPSHOT.read_text()
    assert_that(render(per_repo=_SAMPLE, data_as_of="Jul 17, 2026")).is_equal_to(
        expected,
    )


def test_render_light_uses_light_surface_and_no_dark_surface() -> None:
    """The light variant paints the light surface and track, not the dark ones."""
    svg = render(per_repo=_SAMPLE, theme=LIGHT)
    assert_that(svg).contains(f'fill="{LIGHT.surface}"')
    assert_that(svg).contains(f'fill="{LIGHT.track}"')
    assert_that(svg).does_not_contain(DARK.surface)
    assert_that(svg).does_not_contain(DARK.track)


def test_render_default_theme_is_dark() -> None:
    """Omitting the theme keeps the original dark surface (zero drift)."""
    svg = render(per_repo=_SAMPLE)
    assert_that(svg).contains(f'fill="{DARK.surface}"')


def test_render_is_wellformed_svg() -> None:
    """Output is a self-contained SVG document at the compact ~700x260 size."""
    svg = render(per_repo=_SAMPLE)
    assert_that(svg).starts_with("<svg")
    assert_that(svg).ends_with("</svg>")
    assert_that(svg).contains('viewBox="0 0 700 260"')
    assert_that(svg).contains('role="img"')


def test_render_stamps_the_data_as_of_date() -> None:
    """A supplied ``data_as_of`` label renders as a muted footer stamp and grows
    the panel to fit it."""
    svg = render(per_repo=_SAMPLE, data_as_of="Jul 17, 2026")
    assert_that(svg).contains("data as of Jul 17, 2026")
    assert_that(svg).contains('viewBox="0 0 700 282"')


def test_render_omits_stamp_without_data_as_of() -> None:
    """No stamp is rendered when ``data_as_of`` is omitted."""
    svg = render(per_repo=_SAMPLE)
    assert_that(svg).does_not_contain("data as of")


def test_fold_math_eleven_repos_yields_eight_bars_plus_fold() -> None:
    """Eleven repos with top_n=8 render eight bars and one fold row."""
    svg = render(per_repo=_SAMPLE, top_n=8)
    assert_that(svg.count('class="repo-row"')).is_equal_to(8)
    assert_that(svg.count('class="repo-row fold"')).is_equal_to(1)


def test_fold_row_sums_the_remainder() -> None:
    """The fold row's count equals the sum of repos beyond top_n."""
    svg = render(per_repo=_SAMPLE, top_n=8)
    # gists + sandbox + archive-old = 12 + 7 + 3 = 22
    assert_that(svg).contains("everything else")
    assert_that(svg).contains(">22</text>")
    assert_that(svg).contains(_FOLD_COLOR)


def test_no_fold_row_when_within_top_n() -> None:
    """Fewer repos than top_n render no fold row."""
    data = {"a": 5, "b": 3, "c": 1}
    svg = render(per_repo=data, top_n=8)
    assert_that(svg.count('class="repo-row"')).is_equal_to(3)
    assert_that(svg.count('class="repo-row fold"')).is_equal_to(0)
    assert_that(svg).does_not_contain("everything else")
    assert_that(svg).does_not_contain(_FOLD_COLOR)


def test_label_truncation_applies_ellipsis() -> None:
    """A repo name longer than the label budget is truncated with an ellipsis."""
    long_name = "infra-pipeline-orchestrator-service"
    svg = render(per_repo={long_name: 10}, top_n=8)
    # The visible name label is truncated to a single-ellipsis form ...
    assert_that(svg).contains(">infra-pipeline-orch…</text>")
    assert_that(svg).does_not_contain(f">{long_name}</text>")
    # ... while the full name is preserved in the row's hover tooltip.
    assert_that(svg).contains(f"<title>{long_name}: 10</title>")


def test_short_labels_are_not_truncated() -> None:
    """A repo name within the label budget is rendered verbatim."""
    svg = render(per_repo={"git-replay": 10}, top_n=8)
    assert_that(svg).contains(">git-replay</text>")
    assert_that(svg).does_not_contain("…")


def test_palette_order_is_load_bearing() -> None:
    """Bars take the CVD-validated palette in order for the top repos."""
    data = {name: 100 - i for i, name in enumerate("abcdefghi")}
    svg = render(per_repo=data, top_n=8)
    for color in _PALETTE[:8]:
        assert_that(svg).contains(f'fill="{color}"')


def test_bars_scale_to_largest_rendered_value() -> None:
    """The top repo's bar spans the full track width."""
    svg = render(per_repo={"top": 100, "next": 50}, top_n=8)
    # _BAR_MAX_W is 460.0; the max-valued bar reaches it.
    assert_that(svg).contains('class="bar" data-i="0" x="180.0" y="')
    assert_that(svg).contains('width="460.0"')


def test_counts_are_right_aligned() -> None:
    """Count labels anchor to the right edge of the count column."""
    svg = render(per_repo={"repo": 7})
    assert_that(svg).contains('class="count" x="676.0" y=')
    assert_that(svg).contains('text-anchor="end"')


def test_names_are_right_aligned() -> None:
    """Name labels anchor to the right edge of the name column."""
    svg = render(per_repo={"repo": 7})
    assert_that(svg).contains('class="name" x="168.0"')


def test_empty_input_renders_valid_svg_without_rows() -> None:
    """An empty mapping still produces a valid, row-free SVG."""
    svg = render(per_repo={})
    assert_that(svg).starts_with("<svg")
    assert_that(svg).ends_with("</svg>")
    assert_that(svg).does_not_contain('class="repo-row"')


def test_special_characters_are_escaped() -> None:
    """Repo names with XML-significant characters are escaped in output."""
    svg = render(per_repo={"a&b<c>": 3})
    assert_that(svg).contains("a&amp;b&lt;c&gt;")
    assert_that(svg).does_not_contain("a&b<c>")


def test_render_pinned_matches_snapshot() -> None:
    """The pinned-row output is byte-for-byte stable against its snapshot."""
    expected = _SNAPSHOT_PINNED.read_text()
    svg = render(
        per_repo=_SAMPLE,
        data_as_of="Jul 17, 2026",
        pinned=("git-replay", "sandbox", "archive-old"),
    )
    assert_that(svg).is_equal_to(expected)


def test_pinned_below_threshold_gets_a_named_row() -> None:
    """A pinned repo outside the top-N is promoted to its own named row."""
    # sandbox (7) and archive-old (3) fall in the fold tail below top 8.
    svg = render(per_repo=_SAMPLE, top_n=8, pinned=("sandbox", "archive-old"))
    assert_that(svg).contains("<title>sandbox: 7</title>")
    assert_that(svg).contains("<title>archive-old: 3</title>")
    # Two pinned rows join the eight top-N rows for ten named rows.
    assert_that(svg.count('class="repo-row"')).is_equal_to(10)


def test_pinned_rows_follow_top_n_in_count_order() -> None:
    """Pinned rows are placed after the top-N in descending-count order."""
    svg = render(per_repo=_SAMPLE, top_n=8, pinned=("archive-old", "sandbox"))
    # blog is the last top-N row; the pinned rows follow it, sandbox before
    # archive-old because 7 > 3 regardless of the pinned argument order.
    blog = svg.index("<title>blog: 19</title>")
    sandbox = svg.index("<title>sandbox: 7</title>")
    archive = svg.index("<title>archive-old: 3</title>")
    assert_that(blog).is_less_than(sandbox)
    assert_that(sandbox).is_less_than(archive)


def test_pinned_in_top_n_is_not_duplicated() -> None:
    """A pinned repo already within the top-N renders exactly one row."""
    svg = render(per_repo=_SAMPLE, top_n=8, pinned=("git-replay",))
    assert_that(svg.count("<title>git-replay: 128</title>")).is_equal_to(1)
    # No pinned promotion happened, so the fold tail is unchanged (3 more).
    assert_that(svg.count('class="repo-row"')).is_equal_to(8)
    assert_that(svg).contains(">22</text>")


def test_fold_sum_excludes_pinned_repos() -> None:
    """The fold row sums only the non-pinned remainder beyond top-N."""
    # Tail is gists (12) + sandbox (7) + archive-old (3); pinning the latter
    # two leaves the fold row summing gists alone.
    svg = render(per_repo=_SAMPLE, top_n=8, pinned=("sandbox", "archive-old"))
    assert_that(svg).contains("everything else")
    assert_that(svg).contains(">12</text>")
    assert_that(svg).does_not_contain(">22</text>")


def test_pinned_absent_from_per_repo_is_ignored() -> None:
    """A pinned name missing from the data adds no row."""
    svg = render(per_repo=_SAMPLE, top_n=8, pinned=("not-a-real-repo",))
    assert_that(svg.count('class="repo-row"')).is_equal_to(8)
    assert_that(svg).does_not_contain("not-a-real-repo")


def test_no_fold_row_when_all_remainder_is_pinned() -> None:
    """Pinning the entire tail leaves no repo to fold."""
    svg = render(
        per_repo=_SAMPLE,
        top_n=8,
        pinned=("gists", "sandbox", "archive-old"),
    )
    assert_that(svg).does_not_contain("everything else")
    assert_that(svg.count('class="repo-row fold"')).is_equal_to(0)
    assert_that(svg.count('class="repo-row"')).is_equal_to(11)


# pytest.mark.parametrize reads as untyped under lintro's dependency-free mypy env
@pytest.mark.parametrize(
    "top_n",
    [0, -1],
    ids=["zero", "negative"],
)
def test_render_rejects_non_positive_top_n(top_n: int) -> None:
    """A non-positive ``top_n`` is a programming error."""
    with pytest.raises(ValueError):
        render(per_repo={"a": 1}, top_n=top_n)
