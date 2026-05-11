#!/usr/bin/env bash
# Seed a new Knowledge Base instance from a git repo
# Run after cloning the knowledge base repo

set -euo pipefail

KBK_HOME="${KBK_HOME:-${HOME}/knowledge-base}"
SSH_KEY="${HOME}/.ssh/id_ed25519"

echo "=== Knowledge Base Kit — Seed ==="

if [ ! -d "${KBK_HOME}/.git" ]; then
    echo "Directory not a git repo. Cloning..."
    if [ -f "${SSH_KEY}" ]; then
        GIT_SSH_COMMAND="ssh -i ${SSH_KEY}" git clone git@github.com:Wendigooor/knowledge-base.git "${KBK_HOME}"
    else
        git clone https://github.com/Wendigooor/knowledge-base.git "${KBK_HOME}"
    fi
fi

cd "${KBK_HOME}"

echo "[1/3] Installing kbk..."
pip install -e . 2>/dev/null || pip install knowledge-base-kit 2>/dev/null

echo "[2/3] Initializing knowledge base..."
mkdir -p exports snapshots
kbk init --path "${KBK_HOME}"

echo "[3/3] Seeding ChromaDB..."
if [ -f "exports/chromadb-export.json" ]; then
    kbk seed --seed-file "exports/chromadb-export.json"
else
    echo "  No export found — starting with empty database"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Add your first document:"
echo "     kbk add --collection default --id \"hello\" --content \"Knowledge Base Kit ready\""
echo "  2. Search:"
echo "     kbk search \"knowledge base\""
echo "  3. Set up cron for auto-sync:"
echo "     crontab -e"
echo "     */30 * * * * ${KBK_HOME}/scripts/sync.sh"
