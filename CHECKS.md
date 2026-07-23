# Checks

Run the smallest relevant checks before calling work done.

## Commands
- `./venv/bin/python watch.py` — one full poll cycle (~2.5 min with seat
  checks); expect "ok: N shows ... M seat-checked" on stdout, fresh `status.txt`.
- `launchctl list | grep odyssey` — agent loaded.
- `tail logs/watch.log` — last scheduled run succeeded.

## Manual checks
- A macOS notification banner actually appeared (seed run).
- `status.txt` lists plausible showtimes for the resolved theatres.
- After any edit to watch.py: state.json survives a run without false "new
  show" alerts (run twice; second run should report 0 new).
- After any edit to render.py: open docs/index.html — chips/badges render,
  dark mode legible, spotlight matches status.txt good-seat lines.
- After a push: https://jkobygold.github.io/odyssey-imax-tracker/ shows the
  new timestamp (Pages builds take ~1 min).
