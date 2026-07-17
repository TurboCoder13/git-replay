"""Standalone interactive HTML replay page renderer for git-replay.

Ports the project's HTML prototype into a templated, tested renderer. The page
is fully self-contained: all CSS and JavaScript are inlined and there are no
external resource references, so it can be deployed to GitHub Pages as a single
``index.html``.

The page bakes the aggregated commit data into inline JSON and drives four
coordinated widgets from a single ``requestAnimationFrame`` playhead:

* a replay panel — a JS-driven timeline of churn bars, live commit and
  lines-written counters, a ticker log of the biggest commits, and a replay
  button;
* per-repo live bars whose counters advance as the playhead passes each repo's
  commits;
* a daily commit heatmap, embedded from :mod:`git_replay.render.heatmap_svg`;
* an author panel with the settled *agent-authored* framing.

The replay autoplays once via an ``IntersectionObserver`` at ~35% visibility,
and ``prefers-reduced-motion`` collapses every animation to its final state.

Data reductions are consumed from :mod:`git_replay.aggregate`; author
normalization and parsing come from :mod:`git_replay.model`. This module owns
only the page-specific presentation and the inline interactive SVG/JS that the
static SVG renderers cannot express.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, tzinfo

from git_replay.aggregate import (
    Bucket,
    bucketize,
    daily_counts,
    per_author,
    per_repo,
    split_authors,
)
from git_replay.model import Commit
from git_replay.render import heatmap_svg
from git_replay.render.palette import lerp

_N_BUCKETS = 240
_DURATION_MS = 30_000
_TICKER_TOP = 90
_TICKER_SUBJECT_MAX = 96
_BOT_MARKER = "[bot]"

# Inline replay-SVG geometry (distinct from the standalone replay_svg widget:
# this canvas is driven by page JavaScript, not CSS keyframes).
_SVG_WIDTH = 760.0
_BASELINE = 118.0
_BAR_TOP_PAD = 8.0
_BAR_GAP = 0.9
_MIN_BAR_HEIGHT = 3.0
_CYAN = (34, 211, 238)
_PINK = (244, 114, 182)
_ZERO_CHURN_FILL = "rgb(60,66,80)"

# Categorical palette — CVD-validated order against the #10131a surface, shared
# with the static repo/author widgets. Row i takes _CATEGORICAL[i]; any overflow
# takes _TAIL.
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
_TAIL = "#475569"

_MONO = "ui-monospace,SFMono-Regular,Menlo,monospace"
_STYLE = f"""\
*,*::before,*::after {{ box-sizing:border-box; }}
:root {{ color-scheme: dark; }}
html {{ background:#0a0c10; }}
body {{ background:#0a0c10; color:#d3d9e3; margin:0; padding:48px 20px 80px;
  font-family:ui-sans-serif,system-ui,-apple-system,sans-serif; }}
.wrap {{ max-width:880px; margin:0 auto; display:flex; flex-direction:column;
  gap:40px; }}
.eyebrow {{ font-family:{_MONO}; font-size:12px; letter-spacing:.22em;
  text-transform:uppercase; color:#8b93a5; }}
h1 {{ font-family:{_MONO}; font-size:clamp(26px,4.5vw,40px); color:#f4f6fa;
  margin:10px 0 4px; text-wrap:balance; letter-spacing:-0.01em; }}
.sub {{ color:#8b93a5; font-size:15px; max-width:62ch; line-height:1.55; margin:0; }}
.panel {{ background:#10131a; border:1px solid #1f2430; border-radius:14px;
  overflow:hidden; }}
.panel-head {{ display:flex; flex-wrap:wrap; align-items:center; gap:14px 22px;
  padding:20px 24px 6px; }}
.panel-body {{ padding:8px 24px 20px; }}
.panel-foot {{ border-top:1px solid #1f2430; padding:14px 24px; color:#8b93a5;
  font-size:13.5px; line-height:1.55; }}
.k {{ font-family:{_MONO}; letter-spacing:.18em; font-size:11.5px;
  text-transform:uppercase; color:#6b7385; }}
.big {{ font-family:{_MONO}; font-size:clamp(28px,4vw,42px); font-weight:700;
  color:#f4f6fa; font-variant-numeric:tabular-nums; line-height:1; }}
.big.pink {{ color:#f472b6; }}
.stat {{ display:flex; flex-direction:column; gap:6px; }}
.spacer {{ flex:1; }}
.r-btn {{ font-family:{_MONO}; font-size:13px; cursor:pointer; color:#d3d9e3;
  background:#171b24; border:1px solid #2a3140; border-radius:8px;
  padding:7px 14px; }}
.r-btn:hover {{ border-color:#4a5568; color:#fff; }}
.r-btn:focus-visible {{ outline:2px solid #f472b6; outline-offset:2px; }}
.rb {{ opacity:.12; }}
.rb.on {{ opacity:1; }}
.r-log-box {{ background:#0c0f15; border:1px solid #1c212c; border-radius:10px;
  padding:12px 16px; margin-top:14px; font-family:{_MONO}; font-size:12.5px; }}
.r-log {{ display:flex; gap:12px; white-space:nowrap; overflow:hidden;
  line-height:1.9; color:#98a1b3; }}
.r-log-s {{ flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; }}
.r-log-i {{ color:#4ade80; }} .r-log-d {{ color:#f87171; }}
.r-log-i, .r-log-d {{ font-variant-numeric:tabular-nums; min-width:6ch;
  text-align:right; }}
.hm-scroll {{ overflow-x:auto; }}
.au-row {{ display:flex; align-items:center; gap:14px; padding:5px 0; }}
.au-name {{ width:13rem; text-align:right; font-family:{_MONO}; color:#aeb6c6;
  font-size:12.5px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
  flex-shrink:0; }}
.au-track {{ flex:1; height:12px; }}
.au-bar {{ display:block; height:12px; border-radius:4px; width:0;
  transition:width 1.6s cubic-bezier(.22,.8,.3,1); }}
.rp-bar {{ transition:none; }}
.au-n {{ font-family:{_MONO}; font-size:13px; font-variant-numeric:tabular-nums;
  width:5ch; text-align:right; color:#e7ebf2; }}
@media (prefers-reduced-motion: reduce) {{ .au-bar {{ transition:none; }} }}\
"""


def _esc(text: str) -> str:
    """Escape XML/HTML metacharacters for safe inclusion in markup.

    Args:
        text: Raw text.

    Returns:
        Text with ``&``, ``<``, and ``>`` replaced by their entities.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt(value: int) -> str:
    """Format a commit count with grouped thousands.

    Args:
        value: A non-negative count.

    Returns:
        The count rendered with thousands separators (for example ``1,234``).
    """
    return f"{value:,}"


def _js_embed(obj: object) -> str:
    """Embed a Python object as a JSON string literal parsed at runtime.

    The value is double-encoded (``JSON.parse("...")``) so the browser parses a
    single string literal rather than an inline object graph, and ``</`` is
    escaped so the payload can never terminate the enclosing ``<script>`` block.

    Args:
        obj: Any JSON-serializable object.

    Returns:
        A JavaScript expression string producing the embedded value.
    """
    compact = json.dumps(obj, separators=(",", ":"))
    return json.dumps(compact).replace("</", "<\\/")


def _bar_fill(ins: int, dels: int) -> str:
    """Compute a churn bar's fill from its insertion/deletion ratio.

    The fill interpolates from cyan (all deletions) to pink (all insertions);
    zero-churn buckets render in a neutral gray.

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
        round(lerp(start=_CYAN[channel], end=_PINK[channel], ratio=ratio))
        for channel in range(3)
    )
    return f"rgb({red},{green},{blue})"


def _bar_height(churn: int, max_churn: float) -> float:
    """Scale a bucket's churn to an inline-SVG bar height (square-root scale).

    Args:
        churn: Total lines changed in the bucket.
        max_churn: The largest ``sqrt(churn)`` across all non-empty buckets.

    Returns:
        The bar height in user units, never below the minimum height.
    """
    scaled = math.sqrt(churn) / max_churn * (_BASELINE - _BAR_TOP_PAD)
    return max(_MIN_BAR_HEIGHT, scaled)


def _date_label(timestamp: int, tz: tzinfo) -> str:
    """Render a Unix timestamp as a ``"Mon D, YYYY"`` local-date label.

    Args:
        timestamp: Unix epoch seconds.
        tz: Timezone used to resolve the local date.

    Returns:
        The formatted local date (for example ``Jan 5, 2024``).
    """
    return datetime.fromtimestamp(timestamp, tz).strftime("%b %-d, %Y")


def _repo_order(commits: list[Commit]) -> list[str]:
    """Order repositories by descending commit count, ties broken by name.

    Args:
        commits: The commits to rank.

    Returns:
        Repository names in display order.
    """
    totals = per_repo(commits=commits)
    return [name for name, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))]


def _bucket_index(timestamp: int, start: int, width: float) -> int:
    """Resolve a commit's bucket index on the ``[t0, t1]`` timeline.

    Mirrors :func:`git_replay.aggregate.bucketize` so the JS playhead and the
    baked bars share one bucketing.

    Args:
        timestamp: The commit's Unix timestamp.
        start: The earliest commit timestamp (``t0``).
        width: The per-bucket time width; may be zero when all commits coincide.

    Returns:
        The zero-based bucket index, clamped to the final bucket.
    """
    if width == 0:
        return 0
    return min(_N_BUCKETS - 1, int((timestamp - start) / width))


def _repo_buckets(
    commits: list[Commit],
    order: list[str],
    start: int,
    width: float,
) -> list[list[int]]:
    """Build per-bucket, per-repo commit counts in ``order``.

    Args:
        commits: The commits to distribute.
        order: Repository display order; column ``r`` corresponds to ``order[r]``.
        start: The earliest commit timestamp (``t0``).
        width: The per-bucket time width.

    Returns:
        A ``_N_BUCKETS`` x ``len(order)`` matrix of non-cumulative counts; the
        page's JavaScript accumulates it into a running total.
    """
    index_of = {name: i for i, name in enumerate(order)}
    matrix = [[0] * len(order) for _ in range(_N_BUCKETS)]
    for commit in commits:
        bucket = _bucket_index(timestamp=commit.t, start=start, width=width)
        matrix[bucket][index_of[commit.repo]] += 1
    return matrix


def _ticker(commits: list[Commit], start: int) -> list[list[object]]:
    """Select the biggest agent-authored commits for the replay ticker.

    Service-bot commits are excluded; the top :data:`_TICKER_TOP` by total churn
    are chosen and re-sorted chronologically so the log reveals them in order.

    Args:
        commits: All commits.
        start: The earliest commit timestamp (``t0``).

    Returns:
        A list of ``[offset_ms, "repo: subject", ins, dels]`` rows.
    """
    authored = [c for c in commits if _BOT_MARKER not in c.author]
    ranked = sorted(authored, key=lambda c: -(c.ins + c.dels))[:_TICKER_TOP]
    ranked.sort(key=lambda c: c.t)
    return [
        [
            (c.t - start) * 1000,
            f"{c.repo}: {c.subject}"[:_TICKER_SUBJECT_MAX],
            c.ins,
            c.dels,
        ]
        for c in ranked
    ]


def _bars_svg(buckets: list[Bucket]) -> str:
    """Render one JS-addressable ``<rect>`` per non-empty timeline bucket.

    Args:
        buckets: Chronologically ordered timeline buckets.

    Returns:
        The concatenated ``<rect class="rb">`` markup for the inline replay SVG.
    """
    max_churn = (
        max((math.sqrt(b.ins + b.dels) for b in buckets if b.count), default=0.0) or 1.0
    )
    slot = _SVG_WIDTH / _N_BUCKETS
    rects: list[str] = []
    for index, bucket in enumerate(buckets):
        if not bucket.count:
            continue
        height = _bar_height(churn=bucket.ins + bucket.dels, max_churn=max_churn)
        fill = _bar_fill(ins=bucket.ins, dels=bucket.dels)
        title = f"{bucket.count} commits · +{bucket.ins} −{bucket.dels}"
        rects.append(
            f'<rect class="rb" data-i="{index}" x="{index * slot:.2f}" '
            f'y="{_BASELINE - height:.2f}" width="{slot - _BAR_GAP:.2f}" '
            f'height="{height:.2f}" fill="{fill}">'
            f"<title>{title}</title></rect>",
        )
    return "".join(rects)


def _repo_rows(order: list[str]) -> str:
    """Render the per-repo live-bar rows in display order.

    Args:
        order: Repository names in display order.

    Returns:
        The concatenated ``.au-row`` markup with playhead-driven bars.
    """
    rows = []
    for index, name in enumerate(order):
        color = _CATEGORICAL[index] if index < len(_CATEGORICAL) else _TAIL
        rows.append(
            f'<div class="au-row"><span class="au-name">{_esc(name)}</span>'
            f'<span class="au-track"><span class="au-bar rp-bar" '
            f'style="background:{color}"></span></span>'
            f'<span class="au-n rp-n">0</span></div>',
        )
    return "".join(rows)


def _author_rows(ranked: list[tuple[str, int]], max_count: int) -> str:
    """Render the author panel rows with animated bars and counters.

    Args:
        ranked: Authors sorted by descending commit count.
        max_count: The largest author count, used to scale bar widths.

    Returns:
        The concatenated ``.au-row`` markup for the author panel.
    """
    rows = []
    for index, (name, count) in enumerate(ranked):
        color = _CATEGORICAL[index] if index < len(_CATEGORICAL) else _TAIL
        width = count / max_count * 100 if max_count else 0.0
        rows.append(
            f'<div class="au-row"><span class="au-name">{_esc(name)}</span>'
            f'<span class="au-track"><span class="au-bar" data-w="{width:.1f}" '
            f'style="background:{color}"></span></span>'
            f'<span class="au-n" data-counter-max="{count}">0</span></div>',
        )
    return "".join(rows)


def _peak_week(commits: list[Commit], tz: tzinfo) -> int:
    """Return the highest commit count across local ISO weeks.

    Args:
        commits: The commits to tally.
        tz: Timezone used to resolve each commit's ISO week.

    Returns:
        The peak weekly commit count.
    """
    weekly: dict[tuple[int, int], int] = defaultdict(int)
    for commit in commits:
        iso = datetime.fromtimestamp(commit.t, tz).isocalendar()
        weekly[(iso[0], iso[1])] += 1
    return max(weekly.values())


def _script(
    *,
    buckets: list[Bucket],
    ticker: list[list[object]],
    repo_buckets: list[list[int]],
    repo_totals: list[int],
    start: int,
    span_ms: int,
    total: int,
    total_ins: int,
    max_repo: int,
) -> str:
    """Build the inline ``<script>`` driving the coordinated replay animation.

    Args:
        buckets: Timeline buckets, embedded as ``[count, ins, dels]`` rows.
        ticker: The biggest-commit ticker rows.
        repo_buckets: Per-bucket, per-repo commit counts.
        repo_totals: Final per-repo totals in display order.
        start: The earliest commit timestamp in seconds.
        span_ms: The timeline span in milliseconds.
        total: Total commit count.
        total_ins: Total insertions.
        max_repo: The largest per-repo total, used to scale live bars.

    Returns:
        A complete ``<script>`` element as a string.
    """
    bar_rows = [[b.count, b.ins, b.dels] for b in buckets]
    return f"""<script>
(()=>{{
const buckets=JSON.parse({_js_embed(bar_rows)});
const ticker=JSON.parse({_js_embed(ticker)});
const repoBuckets=JSON.parse({_js_embed(repo_buckets)});
const repoTotals=JSON.parse({_js_embed(repo_totals)});
const T0={start * 1000},TOTAL_MS={span_ms},TOTAL={total};
const TOTAL_INS={total_ins},MAX_REPO={max_repo};
const DUR={_DURATION_MS};
const ease=t=>1-Math.pow(1-t,3);
const num=n=>n.toLocaleString("en-US");
const reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
function onView(root,cb){{
  if(reduced){{cb();return}}
  const io=new IntersectionObserver(es=>{{
    for(const e of es){{if(e.isIntersecting){{io.disconnect();cb();return}}}}
  }},{{threshold:0.35}});
  io.observe(root);
}}
const root=document.getElementById("replay");
const el=s=>root.querySelector(s);
const commitsEl=el(".r-commits"),linesEl=el(".r-lines"),
  headEl=el(".r-playhead"),btn=el(".r-btn"),bars=[...root.querySelectorAll(".rb")],
  logEls=[...root.querySelectorAll(".r-log")];
const repoPanel=document.getElementById("repos");
const rpBars=[...repoPanel.querySelectorAll(".rp-bar")];
const rpNs=[...repoPanel.querySelectorAll(".rp-n")];
const NR=repoTotals.length;
const cumC=[],cumI=[],cumR=[];
{{let cc=0,ci=0;const cr=new Array(NR).fill(0);
for(const b of buckets){{cc+=b[0];ci+=b[1];cumC.push(cc);cumI.push(ci)}}
for(const rb of repoBuckets){{for(let r=0;r<NR;r++)cr[r]+=rb[r];cumR.push([...cr])}}}}
function render(p){{
  const i=Math.min(buckets.length-1,Math.floor(p*buckets.length));
  commitsEl.textContent=num(p>=1?TOTAL:cumC[i]);
  linesEl.textContent="+"+num(p>=1?TOTAL_INS:cumI[i]);
  const px=(p*760).toFixed(1);
  headEl.setAttribute("x1",px);headEl.setAttribute("x2",px);
  for(const r of bars)r.classList.toggle("on",+r.dataset.i<=i);
  const rc=p>=1?repoTotals:cumR[i];
  for(let r=0;r<NR;r++){{
    rpBars[r].style.width=(rc[r]/MAX_REPO*100).toFixed(1)+"%";
    rpNs[r].textContent=num(rc[r]);
  }}
  const ms=p*TOTAL_MS;let hi=-1;
  for(let k=0;k<ticker.length;k++){{if(ticker[k][0]<=ms)hi=k;else break}}
  for(let j=0;j<logEls.length;j++){{
    const k=hi-(logEls.length-1-j),row=logEls[j],
      s=row.querySelector(".r-log-s"),
      pl=row.querySelector(".r-log-i"),mi=row.querySelector(".r-log-d");
    if(k<0){{s.innerHTML="&nbsp;";pl.textContent="";mi.textContent="";continue}}
    s.textContent="· "+ticker[k][1];
    pl.textContent="+"+num(ticker[k][2]);mi.textContent="−"+num(ticker[k][3]);
  }}
}}
let raf=0,played=false;
function play(){{
  cancelAnimationFrame(raf);played=true;
  if(!btn.style.minWidth)btn.style.minWidth=btn.getBoundingClientRect().width+"px";
  btn.textContent="↻ replay";
  if(reduced){{render(1);return}}
  const start=performance.now();
  const step=now=>{{
    const p=Math.min(1,(now-start)/DUR);render(p);
    if(p<1)raf=requestAnimationFrame(step)
  }};
  raf=requestAnimationFrame(step);
}}
btn.addEventListener("click",play);
render(0);
onView(root,()=>{{if(!played)play()}});
const au=document.getElementById("authors");
onView(au,()=>{{
  au.querySelectorAll(".au-bar").forEach(b=>{{
    if(b.dataset.w)b.style.width=b.dataset.w+"%"
  }});
  au.querySelectorAll("[data-counter-max]").forEach(e=>{{
    const target=+e.dataset.counterMax;
    if(reduced){{e.textContent=num(target);return}}
    const start=performance.now();
    const step=now=>{{const p=Math.min(1,(now-start)/1600);
      e.textContent=num(Math.round(ease(p)*target));
      if(p<1)requestAnimationFrame(step)}};
    requestAnimationFrame(step);
  }});
}});
}})();
</script>"""


def render(
    commits: list[Commit],
    tz: tzinfo,
    org_label: str = "TurboCoder13",
) -> str:
    """Render the interactive replay page as a standalone HTML document.

    Assembles the replay panel, per-repo live bars, daily heatmap, and author
    panel into one self-contained page: all CSS and JavaScript are inlined, the
    heatmap is embedded from :mod:`git_replay.render.heatmap_svg`, and the
    aggregated data is baked into the page so the animation needs no network.

    Args:
        commits: The commits to replay; must be non-empty.
        tz: Timezone used to resolve local days and weeks (for the heatmap and
            peak-day/week captions).
        org_label: Human-readable owner label shown in the page eyebrow.

    Returns:
        A complete ``<!doctype html>`` document as a string.

    Raises:
        ValueError: If ``commits`` is empty.
    """
    if not commits:
        raise ValueError("commits must be a non-empty list")

    ordered = sorted(commits, key=lambda c: c.t)
    t0, t1 = ordered[0].t, ordered[-1].t
    total = len(ordered)
    total_ins = sum(c.ins for c in ordered)
    total_dels = sum(c.dels for c in ordered)
    span_days = (t1 - t0) / 86_400
    width = (t1 - t0) / _N_BUCKETS

    buckets = bucketize(commits=ordered, n_buckets=_N_BUCKETS)
    order = _repo_order(commits=ordered)
    repo_total_map = per_repo(commits=ordered)
    repo_totals = [repo_total_map[name] for name in order]
    max_repo = max(repo_totals)
    n_repos = len(order)

    daily = daily_counts(commits=ordered, tz=tz)
    max_day = max(daily.values())
    peak_day = max(daily, key=lambda d: daily[d])
    peak_week = _peak_week(commits=ordered, tz=tz)
    n_years = len({day.year for day in daily})

    author_totals = per_author(commits=ordered)
    ranked_authors = sorted(author_totals.items(), key=lambda kv: (-kv[1], kv[0]))
    max_author = ranked_authors[0][1]
    _agent, bots = split_authors(totals=author_totals)
    bot_commits = sum(bots.values())
    agent_pct = round((total - bot_commits) / total * 100)

    first_label = _date_label(timestamp=t0, tz=tz)
    last_label = _date_label(timestamp=t1, tz=tz)
    span_years = span_days / 365.25

    heatmap = heatmap_svg.render(daily_counts=daily, tz=tz)
    repo_rows = _repo_rows(order=order)
    author_rows = _author_rows(ranked=ranked_authors, max_count=max_author)
    peak_day_label = peak_day.strftime("%b %-d, %Y")
    bar_font = "ui-monospace,Menlo,monospace"

    body = f"""<div class="wrap">
<header>
  <div class="eyebrow">git archaeology · {_esc(org_label)} · {n_repos} repos</div>
  <h1>{_fmt(total)} commits, replayed</h1>
  <p class="sub">Every non-merge commit across {_esc(org_label)}'s public repos,
  {first_label} → {last_label}
  ({span_days:.0f} days). The data is baked into the page; a playhead sweeps it
  back to life.</p>
</header>

<section class="panel" id="replay">
  <div class="panel-head">
    <div class="stat"><span class="k">commits</span>
      <span class="big r-commits">0</span></div>
    <div class="stat"><span class="k">lines written</span>
      <span class="big pink r-lines">+0</span></div>
    <div class="spacer"></div>
    <div class="stat" style="align-items:flex-end">
      <button class="r-btn">▶ replay {span_years:.1f} years in 30s</button>
    </div>
  </div>
  <div class="panel-body">
    <svg viewBox="0 0 760 132" width="100%" role="img"
      aria-label="Commit activity over {span_days:.0f} days; bar height is \
lines changed; pink is mostly additions, cyan is mostly deletions">
      <line x1="0" y1="118.5" x2="760" y2="118.5" stroke="#232936"
        stroke-width="1"></line>
      {_bars_svg(buckets=buckets)}
      <line class="r-playhead" x1="0" y1="0" x2="0" y2="118"
        stroke="#f4f6fa" stroke-width="1.5"></line>
      <text x="2" y="130" fill="#6b7385" font-size="10"
        font-family="{bar_font}">{first_label}</text>
      <text x="758" y="130" fill="#6b7385" font-size="10"
        font-family="{bar_font}" text-anchor="end">{last_label}</text>
    </svg>
    <div class="r-log-box">
      <div class="r-log"><span class="r-log-s">&nbsp;</span>
        <span class="r-log-i"></span><span class="r-log-d"></span></div>
      <div class="r-log"><span class="r-log-s"></span>
        <span class="r-log-i"></span><span class="r-log-d"></span></div>
      <div class="r-log"><span class="r-log-s"></span>
        <span class="r-log-i"></span><span class="r-log-d"></span></div>
    </div>
  </div>
  <div class="panel-foot">All {_fmt(total)} commits (merges excluded), replayed.
  <span style="color:#f472b6">Pink</span> bars are mostly new code;
  <span style="color:#22d3ee">cyan</span>
  bars are mostly deletion; height is lines touched (√ scale). The log shows the
  biggest real commit subjects as the playhead passes them.
  Total churn: +{_fmt(total_ins)} / −{_fmt(total_dels)}.</div>
</section>

<section class="panel" id="repos">
  <div class="panel-head">
    <div class="stat"><span class="k">→ commits land per repo</span>
      <span class="big">{n_repos} repos</span></div>
  </div>
  <div class="panel-body">{repo_rows}</div>
  <div class="panel-foot">Live during the replay above — each repo's counter
  advances as its commits land on the timeline. Canonical clone per repo
  (branch worktrees deduplicated).</div>
</section>

<section class="panel">
  <div class="panel-head">
    <div class="stat"><span class="k">{n_years} years · daily</span>
      <span class="big">{_fmt(total)} commits</span></div>
  </div>
  <div class="panel-body hm-scroll">{heatmap}</div>
  <div class="panel-foot">Every commit bucketed by local day. Peak day:
  {peak_day_label} with {max_day} commits.
  Peak week: {peak_week} commits. Hover a cell for its date.</div>
</section>

<section class="panel" id="authors">
  <div class="panel-head">
    <div class="stat"><span class="k">→ commits land per author</span>
      <span class="big">{agent_pct}% agent-authored</span></div>
  </div>
  <div class="panel-body">{author_rows}</div>
  <div class="panel-foot">The agent-authored commits were authored by Claude Code
  working under human direction and review. The other {_fmt(bot_commits)} commits
  ({100 - agent_pct}%) are service bots: renovate, github-actions, release bots.</div>
</section>
</div>"""

    script = _script(
        buckets=buckets,
        ticker=_ticker(commits=ordered, start=t0),
        repo_buckets=_repo_buckets(commits=ordered, order=order, start=t0, width=width),
        repo_totals=repo_totals,
        start=t0,
        span_ms=(t1 - t0) * 1000,
        total=total,
        total_ins=total_ins,
        max_repo=max_repo,
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(org_label)} · git replay</title>
<style>
{_STYLE}
</style>
</head>
<body>
{body}
{script}
</body>
</html>
"""
