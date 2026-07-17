"""Shared colour primitives for the git-replay renderers.

This module is the single source of truth for the plasma colour ramp used by
the daily commit heatmap and its legend gradient, along with the linear
interpolation helper shared across renderers. Keeping these in one place ensures
every widget samples the exact same colours.
"""

from __future__ import annotations

# Plasma colour stops (matplotlib "plasma" endpoints and quartiles) used as the
# ramp for active cells and the legend gradient.
PLASMA: tuple[tuple[int, int, int], ...] = (
    (13, 8, 135),
    (126, 3, 168),
    (204, 71, 120),
    (248, 149, 64),
    (240, 249, 33),
)


def lerp(
    start: float,
    end: float,
    ratio: float,
) -> float:
    """Linearly interpolate between two values.

    Args:
        start: Value returned when ``ratio`` is 0.
        end: Value returned when ``ratio`` is 1.
        ratio: Interpolation position, typically in ``[0, 1]``.

    Returns:
        The interpolated value ``start + (end - start) * ratio``.
    """
    return start + (end - start) * ratio


def plasma(t: float) -> str:
    """Sample the plasma ramp at position ``t``.

    Args:
        t: Ramp position; clamped to ``[0, 1]``.

    Returns:
        An ``rgb(r,g,b)`` colour string.
    """
    t = max(0.0, min(1.0, t))
    segment = t * (len(PLASMA) - 1)
    index = min(len(PLASMA) - 2, int(segment))
    frac = segment - index
    lo, hi = PLASMA[index], PLASMA[index + 1]
    channels = (round(lerp(start=lo[k], end=hi[k], ratio=frac)) for k in range(3))
    return "rgb({},{},{})".format(*channels)
