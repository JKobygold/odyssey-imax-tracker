#!/usr/bin/env python3
"""Seat-level availability watcher for Regal showtimes (default: The Odyssey in IMAX).

Config-driven (config.json): any US zip code + radius, any movie title substring,
any format filter. Notifies (macOS banner + sound) when:
  - GOOD seats (outside the front rows) open up in a show that had none, or
  - a new matching showtime appears (new dates released), or
  - a previously sold-out show (StopSales=True) reopens.

Also renders docs/index.html + docs/data.json (the public dashboard).

API notes (hard-won — see MEMORY.md):
  - All requests need curl_cffi with impersonate="chrome" (Cloudflare).
  - /api/getSeatPlan must be lowercase; the capitalized path is WAF-blocked.
  - Seat Status: 0=available, 1=sold, 3/7=blocked or accessible seating.
  - RowIndexZeroBased 0 is the BACK row; the front rows (nearest the screen)
    are the HIGHEST indices. "Front" = the front third of rows, per auditorium.
  - Rate limits: keep >=3s between calls; a 429/403 aborts the cycle's
    remaining seat checks and the rotation resumes next cycle.

State lives in state.json (PerformanceId -> last-seen status). Absence of a
performance from one run is NOT treated as removal, so a failed fetch never
causes false "new show" alerts later.
"""

import datetime
import json
import math
import pathlib
import re
import subprocess
import time

from curl_cffi import requests

import render

ROOT = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.json"
STATE_FILE = ROOT / "state.json"
THEATRE_CACHE = ROOT / "theatres_cache.json"
ALERT_LOG = ROOT / "alerts.log"
STATUS_FILE = ROOT / "status.txt"

API = "https://www.regmovies.com/api"
REQUEST_GAP_SECONDS = 3


def log(msg):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def notify(title, message, sound="Glass"):
    script = (
        f'display notification "{message}" '
        f'with title "{title}" sound name "{sound}"'
    )
    subprocess.run(["osascript", "-e", script], check=False)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with ALERT_LOG.open("a") as f:
        f.write(f"[{stamp}] {title}: {message}\n")


def slugify(name):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def haversine_miles(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(math.radians, [la1, lo1, la2, lo2])
    a = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 3956 * 2 * math.asin(math.sqrt(a))


def resolve_theatres(sess, cfg):
    """Zip + radius (+ extra_theatres) -> {code: {name, city, state, slug}}. Cached 7 days."""
    key = {"zip": cfg["zip"], "radius_miles": cfg["radius_miles"],
           "extra_theatres": sorted(cfg.get("extra_theatres", []))}
    if THEATRE_CACHE.exists():
        cache = json.loads(THEATRE_CACHE.read_text())
        age_days = (time.time() - cache.get("resolved_at", 0)) / 86400
        if cache.get("key") == key and age_days < 7:
            return cache["theatres"]

    r = sess.get(f"{API}/theatres", timeout=30)
    r.raise_for_status()
    all_theatres = {t["TheatreCode"]: t for t in r.json()}
    time.sleep(REQUEST_GAP_SECONDS)

    rz = requests.get(f"https://api.zippopotam.us/us/{cfg['zip']}", timeout=30)
    rz.raise_for_status()
    place = rz.json()["places"][0]
    lat, lon = float(place["latitude"]), float(place["longitude"])

    picked = {}
    for code, t in all_theatres.items():
        if haversine_miles(lat, lon, t["Latitude"], t["Longitude"]) <= cfg["radius_miles"]:
            picked[code] = t
    for code in cfg.get("extra_theatres", []):
        if code in all_theatres:
            picked[code] = all_theatres[code]

    theatres = {
        code: {"name": t["Name"], "city": t["City"], "state": t["State"],
               "slug": f"{slugify(t['Name'])}-{code}"}
        for code, t in picked.items()
    }
    THEATRE_CACHE.write_text(json.dumps(
        {"key": key, "resolved_at": time.time(), "theatres": theatres}, indent=1))
    log(f"resolved {len(theatres)} theatres for zip {cfg['zip']} (+{len(cfg.get('extra_theatres', []))} extra)")
    return theatres


def collect_showtimes(sess, cfg, theatres):
    """Return {pid: record} for all matching performances found."""
    perfs = {}
    failures = 0
    today = datetime.date.today()
    title_match = cfg["movie"].lower()
    fmt_filter = cfg.get("format_filter", "").lower()
    for i in range(cfg["days_ahead"]):
        date = today + datetime.timedelta(days=i)
        r = sess.get(
            f"{API}/getShowtimes",
            params={"theatres": ",".join(theatres), "date": date.strftime("%m-%d-%Y"),
                    "hoCode": "", "ignoreCache": "false", "moviesOnly": "false"},
            timeout=30,
        )
        if r.status_code != 200:
            log(f"showtimes HTTP {r.status_code} for {date}")
            failures += 1
            time.sleep(REQUEST_GAP_SECONDS * 2)
            continue
        for show in r.json().get("shows", []):
            code = show.get("TheatreCode")
            if code not in theatres:
                continue
            for film in show.get("Film", []):
                if title_match not in film.get("Title", "").lower():
                    continue
                for p in film.get("Performances", []):
                    attrs = p.get("PerformanceAttributes", [])
                    if fmt_filter and not any(fmt_filter in a.lower() for a in attrs):
                        continue
                    pid = str(p["PerformanceId"])
                    perfs[pid] = {
                        "code": code,
                        "theatre": theatres[code]["name"],
                        "when": p.get("CalendarShowTime", ""),
                        "stop_sales": bool(p.get("StopSales")),
                        "fmt": "70mm" if any("70mm" in a for a in attrs) else
                               ("IMAX" if any("imax" in a.lower() for a in attrs) else "2D"),
                    }
        time.sleep(REQUEST_GAP_SECONDS)
    return perfs, failures


def fetch_good_seats(sess, code, pid):
    """Return ({row: free_count} outside the front third, total_free) or None on error.

    Front = the third of rows nearest the screen = HIGHEST RowIndexZeroBased.
    """
    r = sess.get(f"{API}/getSeatPlan",
                 params={"theatreCode": code, "sessionId": pid}, timeout=30)
    if r.status_code != 200:
        return None
    try:
        layout = r.json()["SeatLayoutData"]
    except Exception:
        return None
    if not layout:
        return None
    good = {}
    total = 0
    for area in layout.get("Areas", []):
        rows = [row for row in area.get("Rows", []) if row.get("Seats")]
        if not rows:
            continue
        indices = sorted(row["RowIndexZeroBased"] for row in rows)
        n_front = math.ceil(len(indices) / 3)
        front_indices = set(indices[-n_front:])
        for row in rows:
            free = sum(1 for s in row["Seats"] if s.get("Status") == 0)
            if not free:
                continue
            total += free
            if row["RowIndexZeroBased"] not in front_indices:
                name = row.get("PhysicalName") or "?"
                good[name] = good.get(name, 0) + free
    return good, total


def fmt_show(rec):
    try:
        dt = datetime.datetime.fromisoformat(rec["when"])
        when = dt.strftime("%a %-m/%-d %-I:%M%p").replace("AM", "am").replace("PM", "pm")
    except ValueError:
        when = rec["when"]
    return f"{when} @ {rec['theatre']}"


def fmt_rows(rows):
    return ", ".join(f"{r}×{n}" for r, n in sorted(rows.items()))


def write_status(state):
    now = datetime.datetime.now()
    lines = [f"Updated {now.strftime('%Y-%m-%d %H:%M')}",
             "good = free seats outside the front third of rows", ""]
    shows = [r for pid, r in state.items()
             if pid.isdigit() and r["when"] >= now.isoformat()]
    for rec in sorted(shows, key=lambda r: r["when"]):
        if rec["stop_sales"]:
            avail = "SOLD OUT"
        elif rec.get("good") is None:
            avail = "seats not checked yet"
        elif rec["good"] > 0:
            avail = f"GOOD SEATS: {rec['good']} ({fmt_rows(rec.get('rows', {}))})"
        elif rec.get("total_free", 0) > 0:
            avail = f"front-only ({rec['total_free']} seats)"
        else:
            avail = "full"
        lines.append(f"{fmt_show(rec):55s} [{rec['fmt']:4s}] {avail}")
    STATUS_FILE.write_text("\n".join(lines) + "\n")


def run_seat_checks(sess, state, cursors, budget):
    """Rotate seat checks: 60% of budget on the next 3 days, 40% on the rest."""
    now = datetime.datetime.now()
    horizon = (now + datetime.timedelta(days=3)).isoformat()
    now_iso = now.isoformat()
    future = [pid for pid, r in state.items()
              if pid.isdigit() and r["when"] >= now_iso and not r["stop_sales"]]
    near = sorted((p for p in future if state[p]["when"] < horizon),
                  key=lambda p: state[p]["when"])
    far = sorted((p for p in future if state[p]["when"] >= horizon),
                 key=lambda p: state[p]["when"])

    good_alerts = []
    checked = 0
    aborted = False

    def check_pool(pool, cursor_key, quota):
        nonlocal checked, aborted
        if not pool or quota <= 0 or aborted:
            return
        start = cursors.get(cursor_key, 0) % len(pool)
        rotation = (pool[start:] + pool[:start])[:quota]
        done = 0
        for pid in rotation:
            rec = state[pid]
            result = fetch_good_seats(sess, rec["code"], pid)
            time.sleep(REQUEST_GAP_SECONDS)
            if result is None:
                log(f"seat check failed for {fmt_show(rec)}; aborting seat checks this cycle")
                aborted = True
                break
            good, total = result
            n_good = sum(good.values())
            if rec.get("good") == 0 and n_good > 0:
                good_alerts.append((rec, good))
            rec.update(good=n_good, rows=good, total_free=total,
                       seats_checked_at=datetime.datetime.now().isoformat(timespec="minutes"))
            done += 1
            checked += 1
        cursors[cursor_key] = (start + done) % len(pool)

    check_pool(near, "_cursor_near", max(1, int(budget * 0.6)))
    check_pool(far, "_cursor_far", budget - max(1, int(budget * 0.6)))
    return good_alerts, checked, aborted


def main():
    cfg = json.loads(CONFIG_FILE.read_text())
    sess = requests.Session(impersonate="chrome")
    theatres = resolve_theatres(sess, cfg)

    perfs, failures = collect_showtimes(sess, cfg, theatres)
    if not perfs and failures == cfg["days_ahead"]:
        log("all showtime requests failed; keeping old state")
        return

    first_run = not STATE_FILE.exists()
    raw = {} if first_run else json.loads(STATE_FILE.read_text())
    cursors = {k: v for k, v in raw.items() if k.startswith("_")}
    state = {k: v for k, v in raw.items() if not k.startswith("_")}

    new_shows = []
    reopened = []
    for pid, rec in perfs.items():
        old = state.get(pid)
        if old is None:
            if not first_run:
                new_shows.append(rec)
        else:
            if old["stop_sales"] and not rec["stop_sales"]:
                reopened.append(rec)
            for k in ("good", "rows", "total_free", "seats_checked_at"):
                if k in old:
                    rec[k] = old[k]
        state[pid] = rec

    # prune well-past shows only; recently-started ones are still in Regal's
    # feed, and pruning them early causes false "new show" alerts next run
    cutoff = (datetime.datetime.now() - datetime.timedelta(hours=12)).isoformat()
    state = {pid: r for pid, r in state.items() if r["when"] >= cutoff}

    good_alerts, checked, aborted = run_seat_checks(
        sess, state, cursors, cfg.get("seat_checks_per_cycle", 40))

    STATE_FILE.write_text(json.dumps({**state, **cursors}, indent=1))
    write_status(state)
    render.render(state, cfg, theatres, ROOT / "docs")

    if good_alerts:
        parts = [f"{fmt_show(r)}: {sum(g.values())} seats ({fmt_rows(g)})"
                 for r, g in good_alerts[:3]]
        notify("🎟️ GOOD seats opened", "; ".join(parts), sound="Hero")
    if reopened:
        shows = "; ".join(fmt_show(r) for r in sorted(reopened, key=lambda r: r["when"])[:3])
        notify("🎬 Show REOPENED", shows, sound="Hero")
    if new_shows:
        shows = "; ".join(fmt_show(r) for r in sorted(new_shows, key=lambda r: r["when"])[:3])
        extra = f" (+{len(new_shows) - 3} more)" if len(new_shows) > 3 else ""
        notify("🎬 New showtimes", shows + extra)
    if first_run:
        notify("Seat watch is live", f"Tracking {len(perfs)} shows. See status.txt")

    log(f"ok: {len(perfs)} shows, {len(new_shows)} new, {len(reopened)} reopened, "
        f"{checked} seat-checked, {len(good_alerts)} good-seat alerts, "
        f"{failures} failed dates{', seat checks aborted' if aborted else ''}")


if __name__ == "__main__":
    main()
