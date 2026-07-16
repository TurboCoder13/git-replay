"""Static SVG renderer for the daily commit heatmap widget.

Ports the prototype's year-block layout: one 53-week by 7-day grid per calendar
year, with 9px cells on a 2px gap. Empty days render as ``#151923``; active days
use a plasma colour ramp scaled by ``0.15 + 0.85 * sqrt(n / max)`` so that even a
single commit is clearly visible while the busiest day saturates the ramp. Each
cell carries a ``<title>`` tooltip and the widget closes with a legend gradient
running from one commit up to the peak day.

The renderer is pure presentation: it consumes the pre-aggregated
:func:`git_replay.aggregate.daily_counts` mapping and emits a self-contained SVG
string with no animation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime, timedelta, tzinfo

# Plasma colour stops (matplotlib "plasma" endpoints and quartiles) used as the
# ramp for active cells and the legend gradient.
_PLASMA: tuple[tuple[int, int, int], ...] = (
    (13, 8, 135),
    (126, 3, 168),
    (204, 71, 120),
    (248, 149, 64),
    (240, 249, 33),
)

_EMPTY_FILL = "#151923"
_LABEL_FILL = "#8b93a5"
_FONT = "ui-monospace,SFMono-Regular,Menlo,monospace"

_CELL = 9
_GAP = 2
_STEP = _CELL + _GAP
_DAYS_PER_WEEK = 7
_YEAR_GAP = 16
_YEAR_HEIGHT = _DAYS_PER_WEEK * _STEP + _YEAR_GAP

_PAD_LEFT = 44
_PAD_TOP = 8
_PAD_RIGHT = 8
_LABEL_GAP = 8

_LEGEND_WIDTH = 120
_LEGEND_HEIGHT = 10
_LEGEND_GAP = 4
_LEGEND_ID = "hm-legend"


def _lerp(
    a: float,
    b: float,
    t: float,
) -> float:
    """Linearly interpolate between ``a`` and ``b``.

    Args:
        a: Start value.
        b: End value.
        t: Interpolation fraction, typically in ``[0, 1]``.

    Returns:
        The interpolated value ``a + (b - a) * t``.
    """
    return a + (b - a) * t


def _plasma(t: float) -> str:
    """Sample the plasma ramp at position ``t``.

    Args:
        t: Ramp position; clamped to ``[0, 1]``.

    Returns:
        An ``rgb(r,g,b)`` colour string.
    """
    t = max(0.0, min(1.0, t))
    segment = t * (len(_PLASMA) - 1)
    index = min(len(_PLASMA) - 2, int(segment))
    frac = segment - index
    lo, hi = _PLASMA[index], _PLASMA[index + 1]
    channels = (round(_lerp(a=lo[k], b=hi[k], t=frac)) for k in range(3))
    return "rgb({},{},{})".format(*channels)


def _cell_fill(
    count: int,
    max_count: int,
) -> str:
    """Resolve the fill colour for a day with ``count`` commits.

    Args:
        count: Commits on the day.
        max_count: Peak commit count across all days (``>= 1``).

    Returns:
        The empty-cell colour when ``count`` is zero, otherwise a plasma colour
        scaled by ``0.15 + 0.85 * sqrt(count / max_count)``.
    """
    if count == 0:
        return _EMPTY_FILL
    return _plasma(0.15 + 0.85 * math.sqrt(count / max_count))


def _week_index(
    day: date,
    jan1: date,
) -> int:
    """Return the zero-based grid column (week) for ``day`` within its year.

    Weeks start on Monday; the partial first week occupies column zero.

    Args:
        day: The day to place.
        jan1: January 1st of ``day``'s year.

    Returns:
        The column index (0-based) for the day.
    """
    return (day.timetuple().tm_yday + jan1.weekday() - 1) // _DAYS_PER_WEEK


def _cell(
    x: int,
    y: int,
    fill: str,
    title: str,
) -> str:
    """Render one day cell as a rounded ``<rect>`` with a ``<title>`` tooltip.

    Args:
        x: Cell x offset in user units.
        y: Cell y offset in user units.
        fill: Cell fill colour.
        title: Tooltip text (already plain, no markup).

    Returns:
        The SVG markup for the cell.
    """
    return (
        f'<rect x="{x}" y="{y}" width="{_CELL}" height="{_CELL}" rx="2" '
        f'fill="{fill}"><title>{title}</title></rect>'
    )


def _day_title(
    day: date,
    count: int,
) -> str:
    """Build the tooltip text for a day cell.

    Args:
        day: The calendar day.
        count: Commits on that day.

    Returns:
        A ``"YYYY-MM-DD: N commit(s)"`` string.
    """
    unit = "commit" if count == 1 else "commits"
    return f"{day.isoformat()}: {count} {unit}"


def _render_year(
    year: int,
    counts: Mapping[date, int],
    max_count: int,
    top: int,
) -> tuple[str, int]:
    """Render a single year's grid block.

    Args:
        year: Calendar year to render.
        counts: Daily commit counts.
        max_count: Peak commit count across all days.
        top: Y offset of the block's top edge.

    Returns:
        A ``(markup, max_week)`` pair where ``max_week`` is the highest column
        index used by the block.
    """
    label_y = top + 3 * _STEP + _CELL
    parts = [
        f'<text x="{_PAD_LEFT - _LABEL_GAP}" y="{label_y}" text-anchor="end" '
        f'fill="{_LABEL_FILL}" font-family="{_FONT}" font-size="11">{year}</text>',
    ]
    jan1 = date(year, 1, 1)
    day = jan1
    max_week = 0
    while day.year == year:
        week = _week_index(day=day, jan1=jan1)
        max_week = max(max_week, week)
        x = _PAD_LEFT + week * _STEP
        y = top + day.weekday() * _STEP
        count = counts.get(day, 0)
        parts.append(
            _cell(
                x=x,
                y=y,
                fill=_cell_fill(count=count, max_count=max_count),
                title=_day_title(day=day, count=count),
            ),
        )
        day += timedelta(days=1)
    return "".join(parts), max_week


def _render_legend(
    max_count: int,
    top: int,
) -> str:
    """Render the ``1 -> max`` legend gradient.

    Args:
        max_count: Peak commit count, shown as the ramp's upper bound.
        top: Y offset of the legend's top edge.

    Returns:
        The SVG markup for the legend row.
    """
    text_y = top + _LEGEND_HEIGHT - 1
    ramp_x = _PAD_LEFT + 12
    max_x = ramp_x + _LEGEND_WIDTH + 6
    unit = "commit" if max_count == 1 else "commits"
    return (
        f'<text x="{_PAD_LEFT}" y="{text_y}" text-anchor="end" '
        f'fill="{_LABEL_FILL}" font-family="{_FONT}" font-size="11">1</text>'
        f'<rect x="{ramp_x}" y="{top}" width="{_LEGEND_WIDTH}" '
        f'height="{_LEGEND_HEIGHT}" rx="{_LEGEND_HEIGHT // 2}" '
        f'fill="url(#{_LEGEND_ID})"></rect>'
        f'<text x="{max_x}" y="{text_y}" fill="{_LABEL_FILL}" '
        f'font-family="{_FONT}" font-size="11">{max_count} {unit}/day</text>'
    )


def _defs() -> str:
    """Build the ``<defs>`` block holding the legend gradient.

    Returns:
        The SVG ``<defs>`` markup with the plasma legend gradient.
    """
    stops = "".join(
        f'<stop offset="{offset}" stop-color="{_plasma(pos)}"></stop>'
        for offset, pos in (("0", 0.15), ("0.33", 0.45), ("0.66", 0.7), ("1", 1.0))
    )
    return (
        f'<defs><linearGradient id="{_LEGEND_ID}" x1="0" y1="0" x2="1" y2="0">'
        f"{stops}</linearGradient></defs>"
    )


def _tz_label(tz: tzinfo) -> str:
    """Return a stable, human-readable label for ``tz``.

    Uses a fixed reference instant so the label does not depend on the current
    date (and therefore stays deterministic across snapshot runs).

    Args:
        tz: Timezone used to bucket commits into local days.

    Returns:
        The timezone's short name, falling back to ``str(tz)``.
    """
    return datetime(2000, 1, 1, tzinfo=tz).tzname() or str(tz)


def render(
    daily_counts: Mapping[date, int],
    tz: tzinfo,
) -> str:
    """Render the daily commit heatmap as a static SVG.

    Args:
        daily_counts: Mapping of local calendar day to commit count, as produced
            by :func:`git_replay.aggregate.daily_counts`.
        tz: Timezone the counts were bucketed in; surfaced in the accessible
            description.

    Returns:
        A self-contained, animation-free SVG document string.
    """
    label = f"Daily commit heatmap by year, local days in {_tz_label(tz=tz)}"
    if not daily_counts:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 20" '
            f'width="120" height="20" role="img" aria-label="{label}"></svg>'
        )

    max_count = max(daily_counts.values())
    years = sorted({day.year for day in daily_counts})

    blocks = []
    max_week = 0
    for offset, year in enumerate(years):
        markup, block_week = _render_year(
            year=year,
            counts=daily_counts,
            max_count=max_count,
            top=_PAD_TOP + offset * _YEAR_HEIGHT,
        )
        blocks.append(markup)
        max_week = max(max_week, block_week)

    legend_top = _PAD_TOP + len(years) * _YEAR_HEIGHT + _LEGEND_GAP
    blocks.append(_render_legend(max_count=max_count, top=legend_top))

    grid_right = _PAD_LEFT + (max_week + 1) * _STEP
    legend_right = _PAD_LEFT + 12 + _LEGEND_WIDTH + 6 + 96
    width = max(grid_right, legend_right) + _PAD_RIGHT
    height = legend_top + _LEGEND_HEIGHT + _LEGEND_GAP + _PAD_TOP

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{label}">'
        f"{_defs()}{''.join(blocks)}</svg>"
    )
