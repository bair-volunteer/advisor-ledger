#!/usr/bin/env bash
# Phase 2 pipeline: fetch -> normalize -> diff -> git commit (if changed).
# Designed to be idempotent and safe to run from a systemd timer.
#
# Exit codes: 0 = ran cleanly (committed or nothing to commit); non-zero = error.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/venv/bin/python"
LOG_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

log() { printf '[%s] %s\n' "$LOG_TS" "$*"; }

log "fetch"
"$PY" scripts/fetch_doc.py

log "normalize"
"$PY" scripts/normalize_doc.py --all

# For each enabled source in config, diff its latest pair if there are >=2 snapshots.
log "diff"
SOURCES="$("$PY" -c '
import json,sys
cfg=json.load(open("config/source_docs.json"))
for s in cfg.get("sources",[]):
  if s.get("enabled"): print(s["source_id"])
')"
for sid in $SOURCES; do
  if [ "$(find normalized -type f -name "*.normalized.json" -path "*/$sid/*" | wc -l)" -ge 2 ]; then
    "$PY" scripts/diff_snapshots.py --latest "$sid" || true
  fi
done

# Commit any new snapshots/ or deltas/. normalized/ is gitignored (derived).
log "git commit"
if [ -d .git ]; then
  git add snapshots deltas 2>/dev/null || true
  if ! git diff --cached --quiet; then
    git commit -m "chore(ledger): pipeline run $LOG_TS" >/dev/null
    log "committed: $(git rev-parse --short HEAD)"
  else
    log "no changes to commit"
  fi
else
  log "no .git — skipping commit"
fi
