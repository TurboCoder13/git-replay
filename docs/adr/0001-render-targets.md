# ADR 0001: Two render targets from one data pipeline

- Status: Accepted
- Date: 2026-07-16
- Deciders: TurboCoder13

## Context

git-replay turns the public git history of configured owners into embeddable widgets.
The primary surface is a GitHub **profile README**, and that surface imposes hard
constraints that shape the whole architecture.

- **READMEs strip JavaScript.** GitHub renders README Markdown through a sanitizer that
  removes `<script>`, event handlers, and interactive elements. Anything embedded in a
  README can only be a static asset — most usefully an image. An SVG embedded via
  `<img>` keeps its **CSS animation** (and SMIL), but never runs JavaScript.
- **camo proxies and caches embedded images.** GitHub rewrites external image URLs to
  its `camo` proxy, which fetches, sanitizes, and **caches** the bytes. Two things
  follow: the image must be self-contained (no external fetches at view time), and
  whatever camo cached is what viewers see until its cache expires. A freshly rebuilt
  widget is not visible instantly — **staleness is inherent** and must be accepted
  rather than fought.
- **The full experience wants interactivity.** A replay playhead, live per-repo
  counters, and hover tooltips are the real product. None of that can live in a README.
  It needs a page that runs JavaScript — i.e. GitHub Pages.

The data behind both surfaces is identical: the same aggregated commit history (buckets,
daily counts, per-repo and per-author breakdowns). Computing it twice would invite drift
between what the README teaser shows and what the page shows.

## Decision

**One data pipeline feeds two render targets.**

1. **Animated SVG widgets** — self-contained, **pure-CSS-animated** SVGs (no JavaScript,
   no SMIL for the replay widget), so they survive README sanitization and play through
   camo. These are the teaser embedded directly in profile READMEs as images.
2. **Interactive HTML page** — the full replay (JavaScript playhead, live counters,
   tooltips, `prefers-reduced-motion` fallback) deployed to GitHub Pages. The README
   images link through to it.

Both targets are rendered from the same aggregation layer (`git_replay.aggregate`);
renderers own presentation only, so the two surfaces can never disagree about the
underlying numbers.

**Publishing is GitHub Pages artifact only.** The build output (`dist/`) is **never
committed** to the repository. CI fetches, builds, uploads a Pages artifact, and deploys
it. Publishing triggers are:

- **on merge to `main`** — so the deployed widgets track the code, and
- **a twice-weekly cron** (Mon/Thu 06:00 UTC) — so the widgets refresh as the tracked
  repositories gain commits, without a human in the loop.

**The privacy gate is enforced in fetch code, not configuration.** Repository discovery
(`git_replay.fetch.discover_repos`) hard-filters out any private or fork repository
unconditionally, regardless of what configuration requests. Only public, non-fork
repositories of the configured owners are ever read.

**Authorship framing is "agent-authored"** (settled wording). The stat tile reports the
share of **agent-authored** commits: commits authored by Claude Code working under human
direction, with the remainder attributed to service bots (renovate, github-actions,
release bots). This phrasing is deliberate and is not to be re-litigated per widget.

## Consequences

- **A staleness window is accepted by design.** Between a rebuild and camo's cache
  expiry, README viewers may see older widgets. The twice-weekly cron bounds how stale
  the _source data_ gets; camo bounds how quickly a fresh build becomes visible. Neither
  is treated as a bug.
- **No committed build output.** `dist/` stays out of git history; the Pages artifact is
  the single published copy. This keeps diffs reviewable and avoids churny
  generated-file commits, at the cost of Pages being the only place the rendered output
  exists.
- **Two renderers to keep in step.** The SVG and HTML targets must stay visually
  coherent even though only the page is interactive. Sharing the aggregation layer
  removes _data_ drift; _presentation_ parity is a standing maintenance cost.
- **Privacy is a code invariant.** Because the private/fork filter lives in fetch code
  rather than config, a misconfiguration cannot leak a private repository. The gate is
  testable and cannot be disabled from `config.toml`.
- **CSS-only animation constrains the SVG widgets.** The replay widget cannot use
  JavaScript-driven interactivity in the README; richer interaction is reserved for the
  Pages page. This is the price of playing inside a README.

## Implementation status

The dual-target architecture is partially landed at time of writing:

- **Landed:** the fetch pipeline with its privacy gate, the aggregation layer, and all
  four SVG renderers (replay, heatmap, repos, stat).
- **Not yet merged — [#14](https://github.com/TurboCoder13/git-replay/issues/14):** the
  interactive HTML page (`render/page.py`) and the `git-replay build` command that
  writes `dist/index.html` plus the four `dist/*.svg` files.
- **Not yet merged — [#15](https://github.com/TurboCoder13/git-replay/issues/15):** the
  build-and-deploy workflow (`deploy-pages.yml`) that publishes `dist/` to GitHub Pages
  on merge and on the twice-weekly cron. Until it merges, the Pages URLs referenced by
  the README are not yet live.
