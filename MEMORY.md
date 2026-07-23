# Memory

Short lessons that should change future behavior in this repo.

- Regal's API 429s on rapid requests: keep >=2.5s between calls, one combined
  multi-theatre request per date (`theatres=1329,0379`).
- Plain curl/requests gets Cloudflare 403; must use curl_cffi with
  `impersonate="chrome"`.
- `StopSales` is the only availability flag getShowtimes exposes (True on
  sold-out shows) — and it's nearly useless: shows report "on sale" with only
  front-row seats (or 2 blocked seats) left. Seat maps are the real signal.
- Seat maps: `GET /api/getSeatPlan?theatreCode=X&sessionId=<PerformanceId>` —
  MUST be lowercase `getSeatPlan`; the capitalized path the site's own JS uses
  is WAF-blocked (403 challenge) for non-browser callers. No cart/order needed.
  Seat `Status`: 0=available, 1=sold, 3/7=blocked/accessible.
- Row `PhysicalName` runs A (front, at screen) to H (KoP, 8 rows, 244 seats)
  or O (Warrington, 15 rows). RowIndexZeroBased 0 = BACK row, not front.
- The order-flow endpoints (createOrder, tickets, GetOrderSessionSeatData)
  rate-limit much harder than the read endpoints and are not needed.
- getShowtimes takes comma-separated theatre codes — one request covers a dozen
  theatres. Scanning theatres one-per-request trips 429s in ~25 requests;
  batches of 12 with 15s gaps sail through. Batch first, always.
- All 12 US Regal IMAX 70mm venues (2026-07): 0297 New Rochelle NY, 0347
  Dublin CA, 0615 Nashville TN, 0652 Tigard OR, 0701 Buford GA, 0734 Orlando
  FL, 1010 Irvine CA, 1026 Ontario CA, 1042 Long Beach CA, 1329 King of
  Prussia PA, 1346 Atlanta GA, 1550 Lakewood CO.
