"""Agent-authored stat-tile SVG renderer for git-replay.

Renders a single static, dark-palette stat tile that summarizes commit
authorship: a headline percentage of agent-authored commits alongside the raw
agent and service-bot commit totals. The output is self-contained SVG markup
with no animation and no external font dependencies; every figure uses a
monospace generic stack with tabular numerals so digits stay column-aligned.

The agent/bot split is produced upstream by
:func:`git_replay.aggregate.split_authors`; this module only presents it. The
wording ``"agent-authored"`` is deliberate and settled — the commits were
authored by Claude Code working under human direction, and the remainder are
service bots (renovate, github-actions, release bots).
"""

from __future__ import annotations

from git_replay.render.theme import DARK, Theme

_FONT = "ui-monospace, SFMono-Regular, Menlo, monospace"
_TABULAR = "font-variant-numeric:tabular-nums"

_WIDTH = 700
_HEIGHT = 120
_STAMP_BAND = 24

#: Fixed caption. Wording is a settled product decision; do not paraphrase.
CAPTION = "authored by Claude Code under human direction · rest are service bots"


def _fmt(value: int) -> str:
    """Format a commit count with grouped thousands.

    Args:
        value: A non-negative commit count.

    Returns:
        The count rendered with thousands separators (for example ``1,234``).
    """
    return f"{value:,}"


def _esc(text: str) -> str:
    """Escape text for safe inclusion in SVG/XML character data.

    Args:
        text: Raw text to escape.

    Returns:
        The text with ``&``, ``<``, and ``>`` replaced by XML entities.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(
    agent_pct: int,
    agent_total: int,
    bot_total: int,
    data_as_of: str | None = None,
    theme: Theme = DARK,
) -> str:
    """Render the agent-authored stat tile as standalone SVG markup.

    Produces a ~700x120 dark-palette tile with the headline
    ``"{agent_pct}% agent-authored"``, the fixed :data:`CAPTION`, and the agent
    and service-bot commit totals shown with thousands separators. The markup is
    static and self-contained: no scripts, animation, or external fonts.

    Args:
        agent_pct: Whole-number percentage of agent-authored commits.
        agent_total: Number of agent-authored commits.
        bot_total: Number of service-bot commits.
        data_as_of: Optional formatted max-commit date label (for example
            ``Jul 17, 2026``). When provided, a muted ``data as of`` footer stamp
            is rendered and the tile grows to fit it; ``None`` omits the stamp.
        theme: Colour theme to render with; defaults to :data:`.theme.DARK`.

    Returns:
        A complete ``<svg>`` document as a string.
    """
    pct = f"{agent_pct}%"
    agent_str = _fmt(agent_total)
    bot_str = _fmt(bot_total)
    aria = (
        f"{agent_pct}% of commits are agent-authored: "
        f"{agent_str} agent commits, {bot_str} service-bot commits"
    )
    height = _HEIGHT + (_STAMP_BAND if data_as_of is not None else 0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_WIDTH} {height}" width="{_WIDTH}" '
        f'height="{height}" role="img" aria-label="{_esc(aria)}" '
        f'font-family="{_FONT}">',
        f"<title>{_esc(aria)}</title>",
        f"<desc>{_esc(CAPTION)}</desc>",
        f'<rect x="0.5" y="0.5" width="{_WIDTH - 1}" height="{height - 1}" '
        f'rx="14" fill="{theme.surface}" stroke="{theme.border}"/>',
        f'<text x="28" y="30" font-size="11" letter-spacing="0.18em" '
        f'fill="{theme.label}">COMMIT AUTHORSHIP</text>',
        f'<text x="28" y="70" font-size="32" style="{_TABULAR}">'
        f'<tspan fill="{theme.accent}" font-weight="700">{pct}</tspan>'
        f'<tspan fill="{theme.headline}"> agent-authored</tspan></text>',
        f'<text x="28" y="100" font-size="12" fill="{theme.muted}">'
        f"{_esc(CAPTION)}</text>",
        f'<text x="672" y="52" text-anchor="end" font-size="22" '
        f'fill="{theme.headline}" style="{_TABULAR}">{agent_str}</text>',
        f'<text x="672" y="68" text-anchor="end" font-size="10" '
        f'letter-spacing="0.14em" fill="{theme.label}">AGENT COMMITS</text>',
        f'<text x="672" y="94" text-anchor="end" font-size="22" '
        f'fill="{theme.value}" style="{_TABULAR}">{bot_str}</text>',
        f'<text x="672" y="110" text-anchor="end" font-size="10" '
        f'letter-spacing="0.14em" fill="{theme.label}">SERVICE-BOT COMMITS</text>',
    ]
    if data_as_of is not None:
        parts.append(
            f'<text x="28" y="{_HEIGHT + 14}" font-size="11" fill="{theme.label}">'
            f"data as of {_esc(data_as_of)}</text>",
        )
    parts.append("</svg>")
    return "\n".join(parts)
