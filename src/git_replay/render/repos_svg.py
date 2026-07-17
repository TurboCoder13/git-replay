"""Compact per-repo bars SVG widget for README-width embedding.

Renders the top-N repositories by commit count as labeled horizontal bars on a
dark panel, folding every repository beyond ``top_n`` into a single
"everything else" row. The categorical palette order is load-bearing: it is
CVD-validated against the dark ``#10131a`` surface and must not be reordered.

The widget is static (no animation) and sized at roughly 700x260 to sit inside a
GitHub profile README. Input is the ``dict[str, int]`` produced by
:func:`git_replay.aggregate.per_repo`.
"""

from __future__ import annotations

# Categorical palette — CVD-validated order against the #10131a surface.
# Do NOT reorder: row i takes _PALETTE[i]; the fold row takes _FOLD_COLOR.
_PALETTE: tuple[str, ...] = (
    "#db2777",
    "#0891b2",
    "#d97706",
    "#7c3aed",
    "#65a30d",
    "#2563eb",
    "#ea580c",
    "#059669",
    "#dc2626",
)
_FOLD_COLOR = "#475569"
_FOLD_LABEL = "everything else"

# Canvas and layout geometry (SVG user units).
_WIDTH = 700.0
_HEIGHT = 260.0
_STAMP_BAND = 22.0
_NAME_RIGHT = 168.0
_BAR_X = 180.0
_BAR_MAX_W = 460.0
_COUNT_RIGHT = 676.0
_ROWS_TOP = 56.0
_ROWS_BOTTOM = 244.0
_BAR_MAX_H = 13.0
_MIN_BAR_W = 2.0
_NAME_MAX_CHARS = 20

# Surface and type colors.
_SURFACE = "#10131a"
_BORDER = "#1f2430"
_EYEBROW_FILL = "#6b7385"
_TITLE_FILL = "#f4f6fa"
_NAME_FILL = "#aeb6c6"
_COUNT_FILL = "#e7ebf2"
_TRACK_FILL = "#171b24"
_MONO = "ui-monospace,SFMono-Regular,Menlo,monospace"


def _esc(text: str) -> str:
    """Escape a string for safe inclusion in SVG text and attributes.

    Args:
        text: Raw text to escape.

    Returns:
        The text with XML-significant characters replaced by entities.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _truncate(name: str) -> str:
    """Truncate a repo name to the label budget, appending an ellipsis.

    Args:
        name: Full repository name.

    Returns:
        The name unchanged when it fits, otherwise a truncated form ending in a
        single-character ellipsis (``…``).
    """
    if len(name) <= _NAME_MAX_CHARS:
        return name
    return name[: _NAME_MAX_CHARS - 1] + "…"


def _row_svg(
    *,
    index: int,
    label: str,
    value: int,
    color: str,
    y_center: float,
    bar_h: float,
    max_value: int,
    is_fold: bool,
) -> str:
    """Render one repo (or fold) row as an SVG group.

    Args:
        index: Zero-based row index within the rendered rows.
        label: Display label (already the raw name; truncation applied here).
        value: Commit count driving the bar width and count text.
        color: Bar fill color.
        y_center: Vertical center of the row in user units.
        bar_h: Bar height in user units.
        max_value: Largest value across rendered rows, used to scale bars.
        is_fold: Whether this is the folded "everything else" row.

    Returns:
        An SVG ``<g>`` fragment for the row.
    """
    display = _FOLD_LABEL if is_fold else _truncate(label)
    frac = 0.0 if max_value <= 0 else value / max_value
    bar_w = max(_MIN_BAR_W, frac * _BAR_MAX_W) if value > 0 else 0.0
    bar_y = y_center - bar_h / 2
    baseline = y_center + 4.0
    classes = "repo-row fold" if is_fold else "repo-row"
    tooltip = f"{_esc(label)}: {value}"
    return (
        f'<g class="{classes}">'
        f"<title>{tooltip}</title>"
        f'<text class="name" x="{_NAME_RIGHT:.1f}" y="{baseline:.1f}" '
        f'text-anchor="end" fill="{_NAME_FILL}" font-size="12.5" '
        f'font-family="{_MONO}">{_esc(display)}</text>'
        f'<rect class="track" x="{_BAR_X:.1f}" y="{bar_y:.1f}" '
        f'width="{_BAR_MAX_W:.1f}" height="{bar_h:.1f}" rx="4" '
        f'fill="{_TRACK_FILL}"/>'
        f'<rect class="bar" data-i="{index}" x="{_BAR_X:.1f}" '
        f'y="{bar_y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="4" '
        f'fill="{color}"/>'
        f'<text class="count" x="{_COUNT_RIGHT:.1f}" y="{baseline:.1f}" '
        f'text-anchor="end" fill="{_COUNT_FILL}" font-size="13" '
        f'font-family="{_MONO}">{value}</text>'
        f"</g>"
    )


def render(
    per_repo: dict[str, int],
    top_n: int = 8,
    data_as_of: str | None = None,
) -> str:
    """Render the compact per-repo bars widget as a standalone SVG string.

    Repositories are sorted by descending commit count (ties broken by name).
    The first ``top_n`` are drawn as individually colored bars; any remaining
    repositories are summed into a single ``"everything else"`` fold row drawn in
    the neutral fold color. Bars are scaled to the largest rendered value so no
    bar overflows the track, and counts are right-aligned.

    Args:
        per_repo: Mapping of repository name to commit count, as produced by
            :func:`git_replay.aggregate.per_repo`.
        top_n: Number of repositories to show individually before folding the
            remainder. Must be positive.
        data_as_of: Optional formatted max-commit date label (for example
            ``Jul 17, 2026``). When provided, a muted ``data as of`` footer stamp
            is rendered and the panel grows to fit it; ``None`` omits the stamp.

    Returns:
        A complete ``<svg>`` document string, ~700x260, static (no animation).

    Raises:
        ValueError: If ``top_n`` is not positive.
    """
    if top_n < 1:
        raise ValueError("top_n must be a positive integer")

    ranked = sorted(per_repo.items(), key=lambda kv: (-kv[1], kv[0]))
    head = ranked[:top_n]
    tail = ranked[top_n:]

    rows: list[tuple[str, int, str, bool]] = [
        (name, count, _PALETTE[i] if i < len(_PALETTE) else _FOLD_COLOR, False)
        for i, (name, count) in enumerate(head)
    ]
    if tail:
        fold_total = sum(count for _, count in tail)
        rows.append((_FOLD_LABEL, fold_total, _FOLD_COLOR, True))

    max_value = max((count for _, count, _, _ in rows), default=0)
    n_rows = len(rows)
    row_h = (_ROWS_BOTTOM - _ROWS_TOP) / n_rows if n_rows else 0.0
    bar_h = min(_BAR_MAX_H, row_h * 0.55) if n_rows else 0.0

    row_svgs = [
        _row_svg(
            index=i,
            label=label,
            value=value,
            color=color,
            y_center=_ROWS_TOP + (i + 0.5) * row_h,
            bar_h=bar_h,
            max_value=max_value,
            is_fold=is_fold,
        )
        for i, (label, value, color, is_fold) in enumerate(rows)
    ]

    shown = len(head)
    subtitle = f"top {shown}" + (f" + {len(tail)} more" if tail else "")
    aria = "Commits per repository"
    if tail:
        aria += (
            f", top {shown} with the remaining {len(tail)} folded into everything else"
        )

    height = _HEIGHT + (_STAMP_BAND if data_as_of is not None else 0.0)
    stamp = ""
    if data_as_of is not None:
        stamp = (
            f'<text x="{_COUNT_RIGHT:.0f}" y="{_HEIGHT + 12:.0f}" text-anchor="end" '
            f'fill="{_EYEBROW_FILL}" font-size="11" font-family="{_MONO}">'
            f"data as of {_esc(data_as_of)}</text>"
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_WIDTH:.0f} {height:.0f}" '
        f'width="{_WIDTH:.0f}" height="{height:.0f}" role="img" '
        f'aria-label="{aria}">'
        f'<rect x="0.5" y="0.5" width="{_WIDTH - 1:.1f}" '
        f'height="{height - 1:.1f}" rx="14" fill="{_SURFACE}" '
        f'stroke="{_BORDER}"/>'
        f'<text x="24" y="30" fill="{_EYEBROW_FILL}" font-size="11.5" '
        f'letter-spacing="0.18em" font-family="{_MONO}">COMMITS PER REPO</text>'
        f'<text x="{_COUNT_RIGHT:.0f}" y="30" text-anchor="end" '
        f'fill="{_TITLE_FILL}" font-size="12.5" font-family="{_MONO}">'
        f"{_esc(subtitle)}</text>"
        f"{''.join(row_svgs)}"
        f"{stamp}"
        f"</svg>"
    )
