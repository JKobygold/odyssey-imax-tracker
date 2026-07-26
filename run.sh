#!/bin/bash
# One watcher cycle, then publish the generated dashboard.
#
# The dashboard (docs/) is a BUILD ARTIFACT, not development history. Publishing
# it as normal commits on main turned the repo into a commit machine and flooded
# the contribution graph with fake activity. Instead we publish docs/ to a
# dedicated 'live' branch as a single rolling, parentless commit, force-pushed
# each cycle and authored by a clearly-labeled bot:
#   - main stays honest human history (docs/ is gitignored there)
#   - 'live' is not the default branch and not 'gh-pages', so it never counts
#     toward contributions; the bot author is a second safeguard
#   - history never accumulates: 'live' is always exactly one deploy commit
# GitHub Pages must be set to serve from branch 'live', folder / (root).
cd "$(dirname "$0")"
./venv/bin/python watch.py >> logs/watch.log 2>&1

publish() {
    git remote get-url origin >/dev/null 2>&1 || return 0
    [ -d docs ] || return 0

    # Build a tree from docs/ using a throwaway index so main's index and
    # working tree are never touched.
    local idx; idx="$(git rev-parse --git-dir)/deploy-index"
    rm -f "$idx"
    GIT_INDEX_FILE="$idx" git add -f docs >> logs/watch.log 2>&1
    local full_tree docs_tree
    full_tree=$(GIT_INDEX_FILE="$idx" git write-tree) || { rm -f "$idx"; return 1; }
    # docs_tree is the site at ROOT, so Pages serves 'live' from / (root).
    docs_tree=$(git rev-parse "$full_tree:docs") || { rm -f "$idx"; return 1; }
    rm -f "$idx"

    # Nothing changed since the last deploy -> no push.
    local last_tree; last_tree=$(git rev-parse -q --verify 'live^{tree}' 2>/dev/null)
    [ "$docs_tree" = "$last_tree" ] && return 0

    local commit
    commit=$(GIT_AUTHOR_NAME="odyssey-watch-bot" GIT_AUTHOR_EMAIL="bot@odyssey.local" \
             GIT_COMMITTER_NAME="odyssey-watch-bot" GIT_COMMITTER_EMAIL="bot@odyssey.local" \
             git commit-tree "$docs_tree" -m "deploy: dashboard $(date -u +%FT%TZ)") || return 1
    git update-ref refs/heads/live "$commit"
    git push -f -q origin live >> logs/watch.log 2>&1 || echo "[deploy push failed]" >> logs/watch.log
}

publish
