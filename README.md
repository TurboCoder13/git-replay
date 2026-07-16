# git-replay

Animated git-history replay widgets — Bun-in-Rust-style commit replays, heatmaps, and
stat tiles rendered as self-animating SVGs for GitHub profile READMEs, plus a full
interactive HTML page deployed to GitHub Pages.

> Skeleton stage. Widgets land here as the
> [v1 milestone](https://github.com/TurboCoder13/git-replay/milestone/1) progresses.

## How it works

One data pipeline, two render targets:

1. **SVG widgets** — CSS/SMIL animation only, so they play inside a GitHub README
   (READMEs strip JavaScript; camo-proxied images allow inline SVG animation).
2. **HTML page** — the full interactive replay (playhead, counters, tooltips) on GitHub
   Pages.

Data covers the public repositories of configured owners, refreshed twice weekly by CI.
Private repositories are excluded at the source.

## Development

```bash
uv sync
uv run lintro chk   # lint
uv run lintro fmt   # format
uv run pytest       # tests
```
