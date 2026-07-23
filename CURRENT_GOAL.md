# Current Goal

## Active goal
Alert Jacob (macOS notification) when GOOD seats — outside the front rows —
open up for Odyssey IMAX at Regal King of Prussia (70mm) or Warrington (laser).
Shows read "on sale" while only front-row seats remain, so seat maps, not the
StopSales flag, are the signal that matters.

## Current task
v2 seat-map layer: per-show getSeatPlan checks (rotating, 30/cycle), alert on
0→N good-seat transitions. Done when launchd runs it every 15 min cleanly.

## Out of scope
- Do not expand the project structure unless the user asks.
- No auto-purchase — notification only (see HUMAN_ONLY.md).

## Last handoff
2026-07-22: v2 — added seat-map layer (getSeatPlan, rotating 30 checks/cycle,
alerts on 0→N good-seat transitions), interval now 15 min. Checks: seed run ok
(127 shows, 30 seat-checked, 0 false alerts); agent reloaded (exit 0);
status.txt shows per-show seat detail. Remaining: KoP alerts will be rare
(true refund-catches); singles vanish in minutes. Unload with
`launchctl bootout gui/501/com.jacob.odyssey-watch` when done.
