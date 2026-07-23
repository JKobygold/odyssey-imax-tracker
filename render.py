"""Render the public dashboard (docs/index.html + docs/data.json) from watcher state.

Written for the average moviegoer: plain language, a Buy link on every row,
seat detail in tooltips. Design follows the dataviz reference palette (status
is icon + label, never color alone; text wears ink tokens; light and dark mode
both authored). No external assets — fully self-contained static page.
"""

import datetime
import html
import json
import pathlib


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


def _rows_tooltip(rows):
    return "; ".join(f"{n} in row {r}" for r, n in sorted(rows.items()))


def _rows_human(rows):
    names = sorted(rows)
    if not names:
        return ""
    if len(names) <= 3:
        return "row " + ", ".join(names) if len(names) == 1 else "rows " + ", ".join(names)
    return f"rows {names[0]}–{names[-1]}"


def _fmt_time(when):
    dt = datetime.datetime.fromisoformat(when)
    return dt.strftime("%-I:%M%p").replace("AM", "am").replace("PM", "pm")


def _fmt_day(when):
    dt = datetime.datetime.fromisoformat(when)
    return dt.strftime("%A %b %-d")


def _fmt_daytime(when):
    dt = datetime.datetime.fromisoformat(when)
    return dt.strftime("%a %-m/%-d %-I:%M%p").replace("AM", "am").replace("PM", "pm")


BADGE_TITLES = {
    "70mm": "IMAX 70mm film — the giant-screen format this movie was shot for. The rarest ticket.",
    "IMAX": "Digital IMAX (laser projection). Still huge, easier to get.",
}


def _badge(fmt):
    title = BADGE_TITLES.get(fmt, "")
    label = "IMAX 70mm" if fmt == "70mm" else fmt
    return f'<span class="badge badge-{fmt.lower()}" title="{html.escape(title)}">{label}</span>'


def _chip(rec):
    st = _status(rec)
    if st == "good":
        tip = _rows_tooltip(rec.get("rows", {}))
        human = _rows_human(rec.get("rows", {}))
        return (f'<span class="chip chip-good" title="{html.escape(tip)}">'
                f'✓ {rec["good"]} decent seats</span> '
                f'<span class="rows">{html.escape(human)} (middle/back)</span>')
    if st == "front":
        return (f'<span class="chip chip-front" title="Seats exist, but only in the very front.">'
                f'⚠ front row only ({rec.get("total_free", 0)} seats)</span>')
    if st == "unknown":
        return '<span class="chip chip-unknown">… checking…</span>'
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

    def theatre_url(code):
        slug = theatres.get(code, {}).get("slug", "")
        return f"https://www.regmovies.com/theatres/{slug}" if slug else movie_url

    shows = {pid: r for pid, r in state.items()
             if pid.isdigit() and r["when"] >= now_iso}

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

    # ---------- how-to strip ----------
    howto = """<section class="howto">
<div class="step"><b>1.</b> Find your theater below — every US Regal showing it in IMAX 70mm is on this page</div>
<div class="step"><b>2.</b> Green <span class="chip chip-good">✓ decent seats</span> means seats in the middle or back are open. Hit <b>Buy</b> fast — they're usually someone's refund and they go in minutes</div>
<div class="step"><b>3.</b> Nothing green? <button id="alert-btn">🔔 Turn on alerts</button> and leave this tab open — your browser will ding when seats open up</div>
<div id="alert-status" class="hint"></div>
</section>"""

    # ---------- spotlight ----------
    if good_now:
        items = "".join(
            f'<li><span class="spot-main"><strong>{_fmt_daytime(r["when"])}</strong> · '
            f'{html.escape(r["theatre"])} {_badge(r["fmt"])}<br>'
            f'<span class="spot-rows">✓ {r["good"]} decent seats · {html.escape(_rows_human(r.get("rows", {})))}</span></span>'
            f'<a class="buy" href="{theatre_url(r["code"])}" rel="nofollow">Buy&nbsp;↗</a></li>'
            for r in good_now[:12]
        )
        spotlight = (f'<section class="spotlight"><h2>🎟️ Book one of these right now</h2>'
                     f'<p class="hint">These showtimes have seats that are NOT in the front row. '
                     f'Soonest first. They will not wait for you.</p><ul>{items}</ul></section>')
    else:
        spotlight = ('<section class="spotlight"><h2>🎟️ Book one of these right now</h2>'
                     '<p class="hint">Nothing at the moment — every non-front seat is taken. '
                     'People cancel constantly, though. Turn on alerts above and leave this tab open; '
                     'we re-check every 15 minutes.</p></section>')

    # ---------- venue sections ----------
    venue_html = []
    for code in venue_order:
        t = theatres.get(code, {})
        name = t.get("name", code)
        city = f'{t.get("city", "")}, {t.get("state", "")}'
        url = theatre_url(code)
        lst = by_venue[code]
        v_good = sum(1 for r in lst if _status(r) == "good")
        fmt_badge = _badge("70mm") if venue_has_70mm(code) else _badge("IMAX")
        good_badge = (f'<span class="chip chip-good">✓ {v_good} showtimes with decent seats</span>'
                      if v_good else '<span class="chip chip-gone">✕ nothing decent right now</span>')
        rows_html = []
        cur_day = None
        for r in lst:
            day = _fmt_day(r["when"])
            if day != cur_day:
                rows_html.append(f'<div class="day">{day}</div>')
                cur_day = day
            checked = r.get("seats_checked_at", "")
            title = f"seats last checked at {checked[-5:]}" if checked else "seat check coming up"
            buy = (f'<a class="buy" href="{url}" rel="nofollow">Buy&nbsp;↗</a>'
                   if _status(r) in ("good", "front") else "")
            rows_html.append(
                f'<div class="show" title="{html.escape(title)}">'
                f'<span class="time">{_fmt_time(r["when"])}</span>'
                f'{_badge(r["fmt"])} {_chip(r)}{buy}</div>'
            )
        open_attr = " open" if v_good else ""
        venue_html.append(
            f'<details class="venue"{open_attr} id="v{code}"><summary>'
            f'<span class="vname"><a href="{url}" rel="nofollow">{html.escape(name)}</a> '
            f'<span class="vcity">{html.escape(city)}</span> {fmt_badge}</span>'
            f'{good_badge}</summary>'
            f'<div class="shows">{"".join(rows_html)}</div>'
            f'<p class="vlink"><a href="{url}" rel="nofollow">Open this theater on regmovies.com ↗</a> '
            f'<span class="muted">(showtimes are in the theater\'s local time)</span></p></details>'
        )

    venue_nav = "".join(
        f'<a class="navchip" href="#v{c}">{html.escape(theatres.get(c, {}).get("city", c))}'
        f'{" · 70mm" if venue_has_70mm(c) else ""}</a>'
        for c in venue_order)

    venue_list_text = "; ".join(
        f'{theatres[c]["name"]} ({theatres[c]["city"]}, {theatres[c]["state"]})'
        for c in venue_order if venue_has_70mm(c) and c in theatres)

    faq = [
        (f"Why is every {movie} IMAX show sold out?",
         f"IMAX 70mm is only playing on a handful of screens in the entire country, and {movie} "
         "is the movie everyone wants to see on them. Shows sell out within minutes of release — "
         "what's usually left is the front row. This page watches the actual seat maps so you can "
         "catch cancellations and newly released showtimes."),
        ("What does “decent seats” mean?",
         "Seats in the middle or back of the theater — anywhere except the front third. The front "
         "rows at a giant-format screen are technically seats, spiritually a neck injury."),
        ("What's the difference between IMAX 70mm and regular IMAX?",
         "IMAX 70mm is the giant film format the movie was shot for — physical film projected on "
         "the biggest screens, and the ticket everyone is fighting over. Plain “IMAX” here means "
         "digital IMAX (laser): still huge, much easier to get into."),
        ("How often does this update?",
         "Roughly every 15 minutes, with the next three days of shows checked most often. Hover "
         "any showtime to see when its seats were last checked."),
        (f"Which theaters show {movie} in IMAX 70mm?",
         f"Regal's 70mm venues tracked here: {venue_list_text}." if venue_list_text
         else "See the venue list on this page."),
        ("Can I track theaters near me, or a different movie?",
         f"Yes — this tracker is open source and works for any US zip code and any movie playing "
         f"at Regal. {repo_url}"),
    ]
    faq_html = "".join(
        f"<details class='faq'><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>"
        for q, a in faq)
    faq_jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})

    title = f"{movie} IMAX 70mm Seat Tracker — Live Ticket Availability at Regal"
    desc = (f"Live seat tracker for {movie} in IMAX and IMAX 70mm. See which Regal showtimes "
            "have decent seats right now — not just the front row — and get an alert when "
            "cancellations open seats up.")
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
.tagline {{ color: var(--ink-2); margin: 0 0 8px; }}
.plain {{ color: var(--ink-2); margin: 0 0 4px; font-size: 0.95rem; }}
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
.spotlight li {{ padding: 10px 0; border-top: 1px solid var(--hairline);
  display: flex; gap: 12px; justify-content: space-between; align-items: center; }}
.spot-rows {{ color: var(--good-text); font-size: 0.88rem; }}
.hint {{ color: var(--ink-2); margin: 0; font-size: 0.9rem; }}
.buy {{ flex-shrink: 0; font-size: 0.92rem; font-weight: 650; padding: 5px 14px;
  border-radius: 8px; background: var(--accent); color: #fff; text-decoration: none; }}
.buy:hover {{ filter: brightness(1.12); }}
.show .buy {{ font-size: 0.8rem; padding: 2px 10px; margin-left: auto; }}
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
.show {{ display: flex; align-items: center; gap: 10px; padding: 4px 0;
  border-top: 1px solid var(--hairline); flex-wrap: wrap; }}
.show .time {{ font-variant-numeric: tabular-nums; min-width: 64px; }}
.show .badge {{ margin-left: 0; }}
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
.howto {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 12px 18px; margin: 18px 0; }}
.howto .step {{ padding: 4px 0; color: var(--ink-2); }}
.howto b {{ color: var(--ink); }}
#alert-btn {{ font: inherit; font-size: 0.9rem; padding: 3px 12px; border-radius: 99px;
  border: 1px solid var(--accent); color: var(--accent); background: none; cursor: pointer; }}
#alert-btn:hover {{ background: var(--accent); color: var(--surface); }}
.vnav {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 14px; }}
.navchip {{ font-size: 0.82rem; padding: 2px 10px; border-radius: 99px;
  border: 1px solid var(--border); color: var(--ink-2); text-decoration: none;
  background: var(--surface); }}
.navchip:hover {{ border-color: var(--accent); color: var(--accent); }}
</style>
</head>
<body>
<main>
<header>
<h1>🎬 Find seats for {html.escape(movie)} in IMAX</h1>
<p class="tagline">An epic about a man trying to get home. A tracker for people trying to get a decent seat.</p>
<p class="plain">Every Regal IMAX 70mm showing of {html.escape(movie)} in the US, with a live look at its
seat map — so you can see which "sold out" shows actually have seats, and which open seats are worth having.</p>
<p class="updated">Updated {updated} ET · this page refreshes itself</p>
</header>

<div class="tiles">
<div class="tile"><div class="n good">{n_good}</div><div class="l">showtimes with decent seats right now</div></div>
<div class="tile"><div class="n">{n_70mm}</div><div class="l">IMAX 70mm showtimes tracked</div></div>
<div class="tile"><div class="n">{n_shows}</div><div class="l">showtimes being watched</div></div>
<div class="tile"><div class="n">{n_venues}</div><div class="l">Regal theaters</div></div>
</div>

{howto}

{spotlight}

<h2>Every theater, every showtime</h2>
<p class="hint">✓ green = seats in the middle or back are open. ⚠ yellow = only the front row is left
(three hours of looking straight up). Jump to your city:</p>
<nav class="vnav">{venue_nav}</nav>
{"".join(venue_html)}

<h2>Questions people yell into search bars</h2>
{faq_html}

<footer>
<p>Updated every ~15 minutes by a computer that also wants to see this movie.
Not affiliated with Regal, IMAX, Universal, or Homer.
Seat data can lag a few minutes — always confirm at checkout.</p>
{f'<p>Open source — <a href="{repo_url}">track any movie in your own zip code</a>.</p>' if repo_url else ''}
</footer>
</main>
<script>
(function () {{
  var KEY = "seatwatch-seen", ON = "seatwatch-on";
  var btn = document.getElementById("alert-btn");
  var status = document.getElementById("alert-status");
  if (!btn) return;
  function setUI() {{
    var on = localStorage.getItem(ON) === "1" && Notification.permission === "granted";
    btn.textContent = on ? "🔔 Alerts are ON" : "🔔 Turn on alerts";
    status.textContent = on
      ? "Alerts on — keep this tab open. You'll get a notification when decent seats appear anywhere."
      : "";
  }}
  if (!("Notification" in window)) {{
    btn.disabled = true;
    btn.textContent = "🔕 Alerts need a desktop browser";
  }} else {{
    btn.onclick = function () {{
      if (localStorage.getItem(ON) === "1") {{
        localStorage.setItem(ON, "0"); setUI(); return;
      }}
      Notification.requestPermission().then(function (p) {{
        if (p === "granted") {{
          localStorage.setItem(ON, "1");
          new Notification("Seat alerts on 🎬", {{ body: "Keep this tab open. We'll ding you when decent seats appear." }});
        }}
        setUI();
      }});
    }};
    setUI();
    setInterval(function () {{
      if (localStorage.getItem(ON) !== "1" || Notification.permission !== "granted") return;
      fetch("data.json?t=" + Date.now()).then(function (r) {{ return r.json(); }}).then(function (d) {{
        var firstPoll = localStorage.getItem(KEY) === null;
        var seen = {{}};
        try {{ seen = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
        var fresh = [];
        (d.good_now || []).forEach(function (s) {{
          var k = s.theatre + "|" + s.when;
          if (!seen[k]) {{ fresh.push(s); }}
          seen[k] = Date.now();
        }});
        Object.keys(seen).forEach(function (k) {{
          if (Date.now() - seen[k] > 259200000) delete seen[k];
        }});
        localStorage.setItem(KEY, JSON.stringify(seen));
        if (fresh.length && !firstPoll) {{
          var f = fresh[0];
          new Notification("🎟️ Decent seats: " + f.theatre, {{
            body: f.when.replace("T", " ").slice(0, 16) + " — " + f.good +
                  " seats" + (fresh.length > 1 ? " (+" + (fresh.length - 1) + " more shows)" : "")
          }});
        }}
      }}).catch(function () {{}});
    }}, 300000);
  }}
}})();
</script>
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
