"""Colour themes shared across the git-replay SVG renderers.

A :class:`Theme` bundles every surface, ink, and accent colour the four
standalone widgets need so the renderers stay palette-agnostic: they read
colours off a passed-in theme rather than hard-coding hex literals. Two themes
ship — :data:`DARK` (the original dark palette; every value is byte-identical to
the historical constants so existing snapshots never change) and :data:`LIGHT`
(a white-surface variant tuned for contrast on light GitHub READMEs).

The plasma ramp used by the heatmap cells and its legend gradient is deliberately
*not* part of the theme: it is a shared, theme-independent ramp owned by
:mod:`git_replay.render.palette`. Only the empty-cell fill behind it changes
between themes.
"""

from __future__ import annotations

from dataclasses import dataclass

# Categorical repo palette — CVD-validated order; readable on both the dark
# ``#10131a`` and light ``#ffffff`` surfaces. Do NOT reorder: row i takes
# ``categorical[i]``; the fold row takes ``Theme.fold``.
_CATEGORICAL: tuple[str, ...] = (
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


@dataclass(frozen=True)
class Theme:
    """A named colour palette threaded through every SVG renderer.

    Attributes:
        name: Short theme identifier (for example ``dark`` or ``light``).
        surface: Panel/tile background fill.
        border: Panel/tile border stroke.
        replay_background: Full-canvas background for the replay widget.
        baseline: Replay timeline baseline stroke.
        track: Repo bar track (unfilled bar) fill.
        heatmap_empty: Fill for heatmap cells with no commits.
        playhead: Replay playhead colour.
        headline: Bright headline/title text.
        value: Numeric value text.
        repo_name: Repository name label text.
        muted: Muted secondary text (heatmap labels, stat caption).
        label: Dim label/eyebrow/footer-stamp text.
        accent: Accent colour for the stat headline percentage.
        zero_churn: Fill for zero-churn replay bars, as an ``rgb(...)`` string.
        fold: Fill for the folded "everything else" repo row.
        cyan: Replay bar endpoint for mostly-deletion buckets, as an RGB triple.
        pink: Replay bar endpoint for mostly-insertion buckets, as an RGB triple.
        categorical: Ordered categorical palette for the top repo bars.
    """

    name: str
    surface: str
    border: str
    replay_background: str
    baseline: str
    track: str
    heatmap_empty: str
    playhead: str
    headline: str
    value: str
    repo_name: str
    muted: str
    label: str
    accent: str
    zero_churn: str
    fold: str
    cyan: tuple[int, int, int]
    pink: tuple[int, int, int]
    categorical: tuple[str, ...]


#: Original dark palette. Every value matches the historical per-renderer
#: constants exactly, so committed snapshots stay byte-for-byte identical.
DARK = Theme(
    name="dark",
    surface="#10131a",
    border="#1f2430",
    replay_background="#0d1017",
    baseline="#232936",
    track="#171b24",
    heatmap_empty="#151923",
    playhead="#f4f6fa",
    headline="#f4f6fa",
    value="#e7ebf2",
    repo_name="#aeb6c6",
    muted="#8b93a5",
    label="#6b7385",
    accent="#f472b6",
    zero_churn="rgb(60,66,80)",
    fold="#475569",
    cyan=(34, 211, 238),
    pink=(244, 114, 182),
    categorical=_CATEGORICAL,
)

#: Light-surface variant. White/off-white surfaces with ``#1f2328`` ink and
#: muted grays; the bar and accent hues are darkened where contrast on white
#: needs it while the shared plasma ramp stays readable.
LIGHT = Theme(
    name="light",
    surface="#ffffff",
    border="#d0d7de",
    replay_background="#ffffff",
    baseline="#d0d7de",
    track="#f6f8fa",
    heatmap_empty="#ebedf0",
    playhead="#1f2328",
    headline="#1f2328",
    value="#1f2328",
    repo_name="#57606a",
    muted="#57606a",
    label="#818b98",
    accent="#be185d",
    zero_churn="rgb(175,184,193)",
    fold="#6e7781",
    cyan=(14, 116, 144),
    pink=(190, 24, 93),
    categorical=_CATEGORICAL,
)
