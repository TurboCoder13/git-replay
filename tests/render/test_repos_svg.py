"""Tests for the compact per-repo bars SVG renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from assertpy import assert_that

from git_replay.render.repos_svg import _FOLD_COLOR, _PALETTE, render

_SNAPSHOT = Path(__file__).parent / "fixtures" / "repos_svg.svg"

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
    assert_that(render(per_repo=_SAMPLE)).is_equal_to(expected)


def test_render_is_wellformed_svg() -> None:
    """Output is a self-contained SVG document at the compact ~700x260 size."""
    svg = render(per_repo=_SAMPLE)
    assert_that(svg).starts_with("<svg")
    assert_that(svg).ends_with("</svg>")
    assert_that(svg).contains('viewBox="0 0 700 260"')
    assert_that(svg).contains('role="img"')


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


# pytest.mark.parametrize reads as untyped under lintro's dependency-free mypy env
@pytest.mark.parametrize(  # type: ignore[untyped-decorator]
    "top_n",
    [0, -1],
    ids=["zero", "negative"],
)
def test_render_rejects_non_positive_top_n(top_n: int) -> None:
    """A non-positive ``top_n`` is a programming error."""
    with pytest.raises(ValueError):
        render(per_repo={"a": 1}, top_n=top_n)
