#!/usr/bin/env bash
# Sync script for Knowledge Base Kit
# Two-way sync: local ChromaDB export → git → pull remote → seed ChromaDB
# Run via cron: */30 * * * * /path/to/scripts/sync.sh

set -euo pipefail

KBK_HOME="${KBK_HOME:-${HOME}/knowledge-base}"
SYNC_LOG="${KBK_HOME}/sync-log.md"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

echo "[${TIMESTAMP}] Starting sync..." >> "${SYNC_LOG}"

cd "${KBK_HOME}"

# === PULL: fetch remote changes ===
echo "  Pulling from remote..." >> "${SYNC_LOG}"
git pull --rebase origin main 2>> "${SYNC_LOG}" || {
    echo "  ⚠️  Pull failed — will retry on next cycle" >> "${SYNC_LOG}"
}

# === SEED: import remote JSON into ChromaDB ===
echo "  Seeding ChromaDB..." >> "${SYNC_LOG}"
kbk seed --seed-file "${KBK_HOME}/exports/chromadb-export.json" 2>> "${SYNC_LOG}" || true

# === EXPORT: export local ChromaDB to JSON ===
echo "  Exporting ChromaDB..." >> "${SYNC_LOG}"
kbk export --export-path "${KBK_HOME}/exports/chromadb-export.json" 2>> "${SYNC_LOG}"

# === PUSH: send local changes ===
if git diff --quiet; then
    echo "  No changes to push" >> "${SYNC_LOG}"
else
    echo "  Committing and pushing..." >> "${SYNC_LOG}"
    git add -A
    git commit -m "sync: ${TIMESTAMP}"
    git push origin main 2>> "${SYNC_LOG}" && echo "  ✅ Pushed" >> "${SYNC_LOG}" || {
        echo "  ⚠️  Push failed (remote may have new changes)" >> "${SYNC_LOG}"
        # Pull again and retry
        git pull --rebase origin main 2>> "${SYNC_LOG}" || true
        git push origin main 2>> "${SYNC_LOG}" && echo "  ✅ Pushed (retry)" >> "${SYNC_LOG}" || true
    }
fi

echo "[${TIMESTAMP}] Sync complete." >> "${SYNC_LOG}"
echo "" >> "${SYNC_LOG}"
