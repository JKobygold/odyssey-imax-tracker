# Decisions

## 2026-07-22 - Public dashboard is static GitHub Pages pushed from the local watcher

Decision: docs/index.html + docs/data.json are rendered locally each cycle and
git-pushed by run.sh; GitHub Pages serves /docs. No server, no client-side API
calls.
Alternatives: a hosted backend (needs a server + would hammer Regal from a
datacenter IP Cloudflare distrusts); client-side fetching (CORS + Cloudflare
block it).
Reason: the Mac already polls; publishing is one commit. Datacenter IPs get
403'd anyway — residential polling is the only reliable data path.
Revisit if: the Mac stops being always-on, or Regal blocks the pattern.

## 2026-07-22 - Repo named odyssey-imax-tracker; local dir stays odyssey-imax-watch

Decision: publish as JKobygold/odyssey-imax-tracker (SEO-friendly name) without
renaming the local directory (launchd plist paths point at it).
Reason: renaming the working install risks breaking a live monitor for zero
functional gain.
Revisit if: the movie run ends and the project generalizes into something else.

## 2026-07-22 - "Front rows" = front third of rows, computed per auditorium

Decision: general rule (highest RowIndexZeroBased third) instead of the v2
hardcoded letters (KoP A-C, Warrington A-E).
Reason: any-zip generalization; the two hardcoded sets are exactly what the
rule computes for those rooms, so behavior is unchanged locally.
Revisit if: a venue's seat-map row indexing turns out not to put the screen at
the highest indices.
