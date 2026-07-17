"""Animated replay-bars SVG renderer for git-replay.

Renders a bucketized commit timeline as a standalone, self-contained SVG whose
animation is expressed entirely in CSS inside the document. Keeping the
animation pure CSS (no JavaScript and no SMIL) is what lets the widget play
when it is embedded as an ``<img>`` in a GitHub README, where it is served
through GitHub's camo image proxy that strips scripts and interactivity.

A playhead sweeps the timeline over 30 seconds on an infinite loop while each
bar flips from dim to lit at an animation delay proportional to its position on
the timeline. A ``prefers-reduced-motion`` block disables every animation and
shows the final, fully lit state.

Bar geometry and colors mirror the project's HTML prototype: heights use a
square-root scale and fills interpolate between cyan (mostly deletions) and
pink (mostly additions). Aggregation is consumed from
:mod:`git_replay.aggregate`; this module only handles presentation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from git_replay.aggregate import Bucket

_WIDTH = 760.0
_HEIGHT = 196.0
_BASELINE = 150.0
_TOP_PAD = 10.0
_LABEL_Y = 172.0
_STAMP_Y = 190.0
_BAR_GAP = 0.9
_MIN_BAR_HEIGHT = 3.0
_SWEEP_SECONDS = 30
_CYAN = (34, 211, 238)
_PINK = (244, 114, 182)
_ZERO_CHURN_FILL = "rgb(60,66,80)"
_BACKGROUND = "#0d1017"
_BASELINE_STROKE = "#232936"
_PLAYHEAD_FILL = "#f4f6fa"
_LABEL_FILL = "#6b7385"
_LABEL_FONT = "ui-monospace,SFMono-Regular,Menlo,monospace"


@dataclass(frozen=True)
class ReplayMeta:
    """Presentation labels for the replay widget.

    Attributes:
        first_label: Human-readable label for the first commit's date.
        last_label: Human-readable label for the last commit's date.
        span_days: Number of days the timeline spans.
    """

    first_label: str
    last_label: str
    span_days: int


def _escape(text: str) -> str:
    """Escape XML metacharacters for safe inclusion in SVG markup.

    Args:
        text: Raw text.

    Returns:
        Text with ``&``, ``<``, and ``>`` replaced by their entities.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _lerp(
    start: float,
    end: float,
    ratio: float,
) -> float:
    """Linearly interpolate between two values.

    Args:
        start: Value returned when ``ratio`` is 0.
        end: Value returned when ``ratio`` is 1.
        ratio: Interpolation position in ``[0, 1]``.

    Returns:
        The interpolated value.
    """
    return start + (end - start) * ratio


def _bar_fill(
    ins: int,
    dels: int,
) -> str:
    """Compute a bar's fill color from its insertion/deletion ratio.

    The fill interpolates from cyan (all deletions) to pink (all insertions).
    Buckets with no line churn render in a neutral gray.

    Args:
        ins: Insertions in the bucket.
        dels: Deletions in the bucket.

    Returns:
        An ``rgb(...)`` CSS color string.
    """
    total = ins + dels
    if total == 0:
        return _ZERO_CHURN_FILL
    ratio = ins / total
    red, green, blue = (
        round(_lerp(start=_CYAN[channel], end=_PINK[channel], ratio=ratio))
        for channel in range(3)
    )
    return f"rgb({red},{green},{blue})"


def _bar_height(
    churn: int,
    max_churn: float,
) -> float:
    """Scale a bucket's churn to a bar height using a square-root scale.

    Args:
        churn: Total lines changed in the bucket.
        max_churn: The largest ``sqrt(churn)`` across all non-empty buckets.

    Returns:
        The bar height in user units, never below the minimum height.
    """
    scaled = math.sqrt(churn) / max_churn * (_BASELINE - _TOP_PAD)
    return max(_MIN_BAR_HEIGHT, scaled)


def _render_bars(buckets: list[Bucket]) -> list[str]:
    """Render one ``<rect>`` per non-empty bucket.

    Args:
        buckets: Chronologically ordered timeline buckets.

    Returns:
        A list of SVG ``<rect>`` element strings, one per non-empty bucket.
    """
    n_buckets = len(buckets)
    if not n_buckets:
        return []
    slot = _WIDTH / n_buckets
    max_churn = (
        max(
            (math.sqrt(bucket.ins + bucket.dels) for bucket in buckets if bucket.count),
            default=0.0,
        )
        or 1.0
    )
    rects: list[str] = []
    for index, bucket in enumerate(buckets):
        if not bucket.count:
            continue
        height = _bar_height(churn=bucket.ins + bucket.dels, max_churn=max_churn)
        x = index * slot
        y = _BASELINE - height
        delay = index / n_buckets * _SWEEP_SECONDS
        title = f"{bucket.count} commits, +{bucket.ins} -{bucket.dels}"
        rects.append(
            f'<rect class="rb" x="{x:.2f}" y="{y:.2f}" '
            f'width="{slot - _BAR_GAP:.2f}" height="{height:.2f}" '
            f'fill="{_bar_fill(ins=bucket.ins, dels=bucket.dels)}" '
            f'style="animation-delay:{delay:.3f}s">'
            f"<title>{title}</title></rect>",
        )
    return rects


def _style_block() -> str:
    """Build the SVG-embedded ``<style>`` block driving the animation.

    Returns:
        A ``<style>`` element string with the sweep and reveal keyframes plus a
        reduced-motion override that shows the final, fully lit state.
    """
    return (
        "<style>\n"
        f".rb{{opacity:.12;animation:rb-reveal {_SWEEP_SECONDS}s linear infinite}}\n"
        f".playhead{{animation:rb-sweep {_SWEEP_SECONDS}s linear infinite}}\n"
        "@keyframes rb-reveal{0%{opacity:.12}3%{opacity:1}100%{opacity:1}}\n"
        "@keyframes rb-sweep{from{transform:translateX(0)}"
        f"to{{transform:translateX({_WIDTH:.0f}px)}}}}\n"
        "@media (prefers-reduced-motion:reduce){"
        ".rb{opacity:1;animation:none}"
        ".playhead{animation:none;opacity:0}}\n"
        "</style>"
    )


def render(
    buckets: list[Bucket],
    meta: ReplayMeta,
) -> str:
    """Render the animated replay-bars widget as a standalone SVG string.

    A muted ``data as of`` footer stamp is drawn from ``meta.last_label`` — the
    max-commit date — so the output stays deterministic (never wall-clock).

    Args:
        buckets: Chronologically ordered timeline buckets to draw.
        meta: Presentation labels for the timeline endpoints and span.

    Returns:
        A complete, self-contained SVG document with CSS-only animation.
    """
    bars = "\n".join(_render_bars(buckets))
    aria_label = _escape(
        f"Commit activity over {meta.span_days} days; bar height is lines changed "
        f"on a square-root scale; pink bars are mostly additions, cyan bars are "
        f"mostly deletions",
    )
    first = _escape(meta.first_label)
    last = _escape(meta.last_label)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_WIDTH:.0f} {_HEIGHT:.0f}" '
        f'width="{_WIDTH:.0f}" height="{_HEIGHT:.0f}" role="img" '
        f'aria-label="{aria_label}">\n'
        f"{_style_block()}\n"
        f'<rect x="0" y="0" width="{_WIDTH:.0f}" height="{_HEIGHT:.0f}" '
        f'fill="{_BACKGROUND}"/>\n'
        f'<line x1="0" y1="{_BASELINE:.1f}" x2="{_WIDTH:.0f}" y2="{_BASELINE:.1f}" '
        f'stroke="{_BASELINE_STROKE}" stroke-width="1"/>\n'
        f"{bars}\n"
        f'<rect class="playhead" x="0" y="{_TOP_PAD:.0f}" width="1.6" '
        f'height="{_BASELINE - _TOP_PAD:.0f}" fill="{_PLAYHEAD_FILL}"/>\n'
        f'<text x="4" y="{_LABEL_Y:.0f}" fill="{_LABEL_FILL}" font-size="11" '
        f'font-family="{_LABEL_FONT}">{first}</text>\n'
        f'<text x="{_WIDTH - 4:.0f}" y="{_LABEL_Y:.0f}" fill="{_LABEL_FILL}" '
        f'font-size="11" font-family="{_LABEL_FONT}" text-anchor="end">{last}</text>\n'
        f'<text x="{_WIDTH / 2:.0f}" y="{_STAMP_Y:.0f}" fill="{_LABEL_FILL}" '
        f'font-size="11" font-family="{_LABEL_FONT}" text-anchor="middle">'
        f"data as of {last}</text>\n"
        f"</svg>\n"
    )
