"""Render the public dashboard (docs/index.html + docs/data.json) from watcher state.

Design follows the dataviz reference palette (status colors are icon + label,
never color alone; text wears ink tokens; light and dark mode both authored).
No external assets — fully self-contained static page, safe for GitHub Pages.
"""

import datetime
import html
import json
import pathlib

STATUS_ORDER = {"good": 0, "front": 1, "unknown": 2, "gone": 3}


def _status(rec):
    if rec["stop_sales"]:
        return "gone"
    if rec.get("good") is None:
        return "unknown"
    if rec["good"] > 0:
        return "good"
    if rec.get("total_free", 0) > 0:
        return "front"
    return "gone"


def _fmt_rows(rows):
    return ", ".join(f"{r}×{n}" for r, n in sorted(rows.items()))


def _fmt_time(when):
    dt = datetime.datetime.fromisoformat(when)
    return dt.strftime("%-I:%M%p").replace("AM", "am").replace("PM", "pm")


def _fmt_day(when):
    dt = datetime.datetime.fromisoformat(when)
    return dt.strftime("%A %b %-d")


def _fmt_daytime(when):
    dt = datetime.datetime.fromisoformat(when)
    return dt.strftime("%a %-m/%-d %-I:%M%p").replace("AM", "am").replace("PM", "pm")


def _chip(rec):
    st = _status(rec)
    if st == "good":
        rows = _fmt_rows(rec.get("rows", {}))
        return f'<span class="chip chip-good">✓ {rec["good"]} good seats</span> <span class="rows">{html.escape(rows)}</span>'
    if st == "front":
        return f'<span class="chip chip-front">⚠ front rows only ({rec.get("total_free", 0)})</span>'
    if st == "unknown":
        return '<span class="chip chip-unknown">… not checked yet</span>'
    return '<span class="chip chip-gone">✕ sold out</span>'


def render(state, cfg, theatres, docs_dir):
    docs = pathlib.Path(docs_dir)
    docs.mkdir(exist_ok=True)
    now = datetime.datetime.now()
    now_iso = now.isoformat()
    movie = cfg.get("movie_display", cfg["movie"].title())
    movie_url = cfg.get("movie_url", "https://www.regmovies.com/")
    site_url = cfg.get("site_url", "")
    repo_url = cfg.get("repo_url", "")

    shows = {pid: r for pid, r in state.items()
             if pid.isdigit() and r["when"] >= now_iso}

    # group by venue
    by_venue = {}
    for pid, r in shows.items():
        by_venue.setdefault(r["code"], []).append(r)
    for lst in by_venue.values():
        lst.sort(key=lambda r: r["when"])

    def venue_has_70mm(code):
        return any(r["fmt"] == "70mm" for r in by_venue[code])

    venue_order = sorted(by_venue, key=lambda c: (
        not venue_has_70mm(c),
        theatres.get(c, {}).get("state", ""),
        theatres.get(c, {}).get("name", ""),
    ))

    good_now = sorted((r for r in shows.values() if _status(r) == "good"),
                      key=lambda r: r["when"])
    n_good = len(good_now)
    n_venues = len(by_venue)
    n_shows = len(shows)
    n_70mm = sum(1 for r in shows.values() if r["fmt"] == "70mm")

    # ---------- spotlight ----------
    if good_now:
        items = "".join(
            f'<li><a href="{movie_url}" rel="nofollow">'
            f'<strong>{_fmt_daytime(r["when"])}</strong> · '
            f'{html.escape(r["theatre"])}'
            f'<span class="badge badge-{r["fmt"].lower()}">{r["fmt"]}</span></a>'
            f'<span class="spot-rows">✓ {r["good"]} good seats — rows {html.escape(_fmt_rows(r.get("rows", {})))}</span></li>'
            for r in good_now[:12]
        )
        spotlight = (f'<section class="spotlight"><h2>🎟️ Grab these now</h2>'
                     f'<p class="hint">Shows with seats outside the front rows, soonest first. '
                     f'They will not wait for you.</p><ul>{items}</ul></section>')
    else:
        spotlight = ('<section class="spotlight"><h2>🎟️ Grab these now</h2>'
                     '<p class="hint">Nothing at the moment — the suitors took everything. '
                     'Refunds drop constantly; we check every 15 minutes. '
                     'Leave this tab open.</p></section>')

    # ---------- venue sections ----------
    venue_html = []
    for code in venue_order:
        t = theatres.get(code, {})
        name = t.get("name", code)
        city = f'{t.get("city", "")}, {t.get("state", "")}'
        slug = t.get("slug", "")
        url = f"https://www.regmovies.com/theatres/{slug}" if slug else movie_url
        lst = by_venue[code]
        v_good = sum(1 for r in lst if _status(r) == "good")
        fmt_badge = ('<span class="badge badge-70mm">IMAX 70mm</span>'
                     if venue_has_70mm(code) else '<span class="badge badge-imax">IMAX</span>')
        good_badge = (f'<span class="chip chip-good">✓ {v_good} shows with good seats</span>'
                      if v_good else '<span class="chip chip-gone">✕ no good seats right now</span>')
        rows_html = []
        cur_day = None
        for r in lst:
            day = _fmt_day(r["when"])
            if day != cur_day:
                rows_html.append(f'<div class="day">{day}</div>')
                cur_day = day
            checked = r.get("seats_checked_at", "")
            title = f'seats checked {checked[-5:]}' if checked else "seat map not fetched yet"
            rows_html.append(
                f'<div class="show" title="{html.escape(title)}">'
                f'<span class="time">{_fmt_time(r["when"])}</span>'
                f'<span class="fmt badge badge-{r["fmt"].lower()}">{r["fmt"]}</span>'
                f'{_chip(r)}</div>'
            )
        open_attr = " open" if v_good else ""
        venue_html.append(
            f'<details class="venue"{open_attr}><summary>'
            f'<span class="vname"><a href="{url}" rel="nofollow">{html.escape(name)}</a> '
            f'<span class="vcity">{html.escape(city)}</span> {fmt_badge}</span>'
            f'{good_badge}</summary>'
            f'<div class="shows">{"".join(rows_html)}</div>'
            f'<p class="vlink"><a href="{url}" rel="nofollow">Book at Regal ↗</a> '
            f'<span class="muted">(times are theatre-local)</span></p></details>'
        )

    venue_list_text = "; ".join(
        f'{theatres[c]["name"]} ({theatres[c]["city"]}, {theatres[c]["state"]})'
        for c in venue_order if venue_has_70mm(c) and c in theatres)

    faq = [
        (f"Why is every {movie} IMAX show sold out?",
         f"IMAX 70mm is only playing on a handful of screens in the entire country, and {movie} "
         "is the movie everyone wants to see on them. Shows sell out within minutes of release — "
         "what's usually left is the front rows. This page watches the seat maps so you can catch "
         "refunds and newly released showtimes."),
        ("What counts as a “good seat”?",
         "Anything outside the front third of the auditorium. The front rows at a giant-format "
         "screen are technically seats, spiritually a neck injury."),
        ("How often does this update?",
         "The tracker polls Regal's seat maps roughly every 15 minutes, prioritizing the next "
         "three days of shows. Each showtime row shows when its seats were last checked (hover)."),
        (f"Which theaters show {movie} in IMAX 70mm?",
         f"Regal's 70mm venues tracked here: {venue_list_text}." if venue_list_text
         else "See the venue list on this page."),
        ("Can I track theaters near me?",
         f"Yes — this tracker is open source and works for any US zip code and any movie. "
         f"Clone it, set your zip in config.json, and run it on your own machine. {repo_url}"),
    ]
    faq_html = "".join(
        f"<details class='faq'><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>"
        for q, a in faq)
    faq_jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})

    title = f"{movie} IMAX 70mm Seat Tracker — Live Ticket Availability at Regal"
    desc = (f"Live seat-map tracker for {movie} in IMAX and IMAX 70mm. See which Regal showtimes "
            "have good seats right now — not just the front row — and catch refund drops and new "
            "ticket releases before they vanish.")
    updated = now.strftime("%b %-d, %-I:%M %p")

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="600">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
{f'<link rel="canonical" href="{site_url}">' if site_url else ''}
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="website">
{f'<meta property="og:url" content="{site_url}">' if site_url else ''}
<meta name="twitter:card" content="summary">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🎬</text></svg>">
<script type="application/ld+json">{faq_jsonld}</script>
<style>
:root {{
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e;
  --muted: #898781; --hairline: #e1e0d9; --border: rgba(11,11,11,0.10);
  --good: #0ca30c; --good-text: #006300; --warn: #fab219; --serious: #ec835a;
  --accent: #2a78d6;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7;
    --muted: #898781; --hairline: #2c2c2a; --border: rgba(255,255,255,0.10);
    --good: #0ca30c; --good-text: #0ca30c; --warn: #fab219; --serious: #ec835a;
    --accent: #3987e5;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--page); color: var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height: 1.5; }}
main {{ max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }}
header h1 {{ font-size: 1.7rem; margin: 0 0 4px; }}
.tagline {{ color: var(--ink-2); margin: 0 0 4px; }}
.updated {{ color: var(--muted); font-size: 0.85rem; }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px; margin: 20px 0; }}
.tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 12px 14px; }}
.tile .n {{ font-size: 1.7rem; font-weight: 650; }}
.tile .l {{ color: var(--ink-2); font-size: 0.82rem; }}
.tile .n.good {{ color: var(--good-text); }}
.spotlight {{ background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 16px 18px; margin: 18px 0; }}
.spotlight h2 {{ margin: 0 0 4px; font-size: 1.15rem; }}
.spotlight ul {{ list-style: none; margin: 10px 0 0; padding: 0; }}
.spotlight li {{ padding: 8px 0; border-top: 1px solid var(--hairline);
  display: flex; flex-wrap: wrap; gap: 4px 12px; justify-content: space-between; }}
.spotlight a {{ color: var(--ink); text-decoration: none; }}
.spotlight a:hover strong {{ text-decoration: underline; }}
.spot-rows {{ color: var(--good-text); font-size: 0.88rem; }}
.hint {{ color: var(--ink-2); margin: 0; font-size: 0.9rem; }}
.chip {{ display: inline-block; font-size: 0.8rem; padding: 1px 8px; border-radius: 99px;
  border: 1px solid var(--border); white-space: nowrap; }}
.chip-good {{ color: var(--good-text); border-color: var(--good); }}
.chip-front {{ color: var(--ink-2); border-color: var(--warn); }}
.chip-gone {{ color: var(--muted); }}
.chip-unknown {{ color: var(--muted); font-style: italic; }}
.rows {{ color: var(--good-text); font-size: 0.82rem; }}
.badge {{ display: inline-block; font-size: 0.7rem; font-weight: 650; padding: 0 6px;
  border-radius: 4px; border: 1px solid var(--border); color: var(--ink-2);
  vertical-align: 1px; margin-left: 6px; }}
.badge-70mm {{ color: var(--accent); border-color: var(--accent); }}
.venue {{ background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; margin: 10px 0; padding: 0; }}
.venue summary {{ cursor: pointer; padding: 12px 16px; display: flex; flex-wrap: wrap;
  gap: 6px 12px; justify-content: space-between; align-items: baseline; }}
.venue summary::-webkit-details-marker {{ display: none; }}
.vname a {{ color: var(--ink); font-weight: 650; text-decoration: none; }}
.vname a:hover {{ text-decoration: underline; }}
.vcity {{ color: var(--muted); font-size: 0.85rem; }}
.shows {{ padding: 0 16px 8px; }}
.day {{ color: var(--ink-2); font-size: 0.82rem; font-weight: 650; margin: 10px 0 2px;
  text-transform: uppercase; letter-spacing: 0.03em; }}
.show {{ display: flex; align-items: baseline; gap: 10px; padding: 4px 0;
  border-top: 1px solid var(--hairline); flex-wrap: wrap; }}
.show .time {{ font-variant-numeric: tabular-nums; min-width: 64px; }}
.show .fmt {{ margin-left: 0; }}
.vlink {{ padding: 6px 16px 12px; margin: 0; font-size: 0.88rem; }}
.vlink a {{ color: var(--accent); }}
.muted {{ color: var(--muted); }}
.faq {{ border-top: 1px solid var(--hairline); padding: 10px 0; }}
.faq summary {{ cursor: pointer; font-weight: 600; }}
.faq p {{ color: var(--ink-2); }}
footer {{ margin-top: 36px; color: var(--muted); font-size: 0.85rem;
  border-top: 1px solid var(--hairline); padding-top: 14px; }}
footer a {{ color: var(--accent); }}
h2 {{ font-size: 1.15rem; margin: 26px 0 6px; }}
</style>
</head>
<body>
<main>
<header>
<h1>🎬 {html.escape(movie)}: IMAX Seat Tracker</h1>
<p class="tagline">An epic about a man trying to get home. A tracker for people trying to get a decent seat.</p>
<p class="updated">Updated {updated} ET · refreshes automatically</p>
</header>

<div class="tiles">
<div class="tile"><div class="n good">{n_good}</div><div class="l">shows with good seats right now</div></div>
<div class="tile"><div class="n">{n_70mm}</div><div class="l">IMAX 70mm shows tracked</div></div>
<div class="tile"><div class="n">{n_shows}</div><div class="l">showtimes watched</div></div>
<div class="tile"><div class="n">{n_venues}</div><div class="l">Regal venues</div></div>
</div>

{spotlight}

<h2>Every venue, every show</h2>
<p class="hint">✓ good seats = anything outside the front third. ⚠ front rows = you will count Matt Damon's pores.
Hover a row for when its seat map was last checked.</p>
{"".join(venue_html)}

<h2>Questions people yell into search bars</h2>
{faq_html}

<footer>
<p>Updated every ~15 minutes by a computer that also wants to see this movie.
Not affiliated with Regal, IMAX, Universal, or Homer.
Seat data comes from Regal's public seat maps and can lag a few minutes — always confirm at checkout.</p>
{f'<p>Open source — <a href="{repo_url}">track any movie in your own zip code</a>.</p>' if repo_url else ''}
</footer>
</main>
</body>
</html>
"""
    (docs / "index.html").write_text(page)

    (docs / "data.json").write_text(json.dumps({
        "updated": now_iso,
        "movie": movie,
        "venues": {code: theatres.get(code, {}) for code in venue_order},
        "good_now": [
            {"when": r["when"], "theatre": r["theatre"], "fmt": r["fmt"],
             "good": r["good"], "rows": r.get("rows", {})}
            for r in good_now],
        "counts": {"good": n_good, "shows": n_shows, "venues": n_venues,
                   "shows_70mm": n_70mm},
    }, indent=1))
