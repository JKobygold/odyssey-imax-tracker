# 🎬 The Odyssey IMAX Seat Tracker

**Live dashboard: <https://jkobygold.github.io/odyssey-imax-tracker/>**

An epic about a man trying to get home. A tracker for people trying to get a
decent seat.

**If you just want to see the movie: use the link above.** No install, no
signup. Find your theater, look for the green ✓ shows, book fast. Click
"🔔 Turn on alerts" and leave the tab open — your browser will ding when good
seats open up. Everything below this line is for people who want to run their
own tracker.

Christopher Nolan's *The Odyssey* in IMAX 70mm is playing on a handful of
screens in the entire country, and every show sells out in minutes — what's
left is the front row, which is not a seat so much as a chiropractic event.
But **refunds drop constantly**. This tool watches Regal's seat maps and tells
you the moment seats outside the front rows open up.

## What it does

- Polls Regal's public showtimes + seat-map APIs every ~15 minutes
- Knows the difference between "on sale" (row A only, lol) and **actually good
  seats** (outside the front third of the auditorium)
- Sends a macOS notification the second good seats appear, a sold-out show
  reopens, or new showtimes are released
- Publishes a static dashboard (GitHub Pages–ready) showing every tracked
  venue and show at a glance

## Not just The Odyssey, not just Philadelphia

Everything is `config.json`:

```json
{
  "zip": "19102",            // your zip code
  "radius_miles": 30,        // how far you'll drive
  "movie": "odyssey",        // title substring to match
  "format_filter": "imax",   // "imax", "70mm", or "" for any format
  "days_ahead": 14,
  "extra_theatres": []       // Regal theatre codes outside your radius
}
```

Any US zip, any movie on regmovies.com, any format. Tickets to the next
hard-to-get thing are also tickets.

## Quickstart

```bash
git clone https://github.com/JKobygold/odyssey-imax-tracker
cd odyssey-imax-tracker
python3 -m venv venv && ./venv/bin/pip install curl_cffi
# edit config.json with your zip
./venv/bin/python watch.py       # one cycle: fetch, diff, notify, render docs/
open docs/index.html
```

To run it on a schedule (macOS), load a LaunchAgent — edit the paths in
`com.jacob.odyssey-watch.plist`, copy it to `~/Library/LaunchAgents/`, and:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jacob.odyssey-watch.plist
```

On Linux, a cron entry running `run.sh` every 15 minutes does the same job.
If the repo has a git remote, `run.sh` auto-commits and pushes the refreshed
dashboard — point GitHub Pages at `/docs` and you have a live public tracker.

## How it works (the fun parts)

- Regal's site sits behind Cloudflare; plain `curl` gets a 403. `curl_cffi`
  with `impersonate="chrome"` gets JSON.
- The showtimes feed's only availability flag (`StopSales`) is nearly useless —
  shows report "on sale" with two seats left in row A. The real signal is
  `/api/getSeatPlan` (lowercase! the capitalized path the site itself uses is
  WAF-blocked), which returns the full seat map, no cart required.
- Seat `Status`: 0 = available, 1 = sold, 3/7 = blocked/accessible.
  `RowIndexZeroBased` 0 is the **back** row; "front" here means the front third
  of rows, computed per auditorium.
- Requests are paced ~3s apart with rotating seat-check budgets (next 3 days
  get 60% of each cycle) to stay polite under Regal's rate limits.

## Disclaimers

Not affiliated with Regal, IMAX, Universal, or Homer. Read-only: it never
creates orders, holds seats, or buys anything — it just looks at the same seat
maps you see at checkout, slightly more often than is dignified. Availability
can lag a few minutes; always confirm at checkout.
