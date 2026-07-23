#!/bin/bash
# One watcher cycle, then publish the dashboard if this is a git repo with a remote.
cd "$(dirname "$0")"
./venv/bin/python watch.py >> logs/watch.log 2>&1

if git rev-parse --git-dir >/dev/null 2>&1 && git remote get-url origin >/dev/null 2>&1; then
    if ! git diff --quiet -- docs/ 2>/dev/null || [ -n "$(git status --porcelain docs/)" ]; then
        git add docs/ >> logs/watch.log 2>&1
        git commit -q -m "data: dashboard update" >> logs/watch.log 2>&1
        git push -q origin main >> logs/watch.log 2>&1 || echo "[push failed]" >> logs/watch.log
    fi
fi
