#!/usr/bin/env bash
# Launch the self-hosted Supermemory server with the native Groq provider path
# -- the config that works for writes + embeddings + chunk/hybrid search, which
# is all we depend on. (The binary's own server-side consolidation agent doesn't
# run on the free Groq tier; we don't rely on it -- consolidation is done by our
# own Consolidation Agent instead. See agents/consolidation.py and memory_explorer.md.)
#
# Always launched from $HOME so the encrypted data dir stays at ~/.supermemory
# and no stray .supermemory/ is created inside the repo.
set -euo pipefail

REPO="/home/vidit-shrimali/Web3Projects/HFT-Agent-Team"

# Load .env so GROQ_API_KEY is present, then export it for the server process.
set -a
# shellcheck disable=SC1091
source "$REPO/.env"
set +a

: "${GROQ_API_KEY:?GROQ_API_KEY not set in .env}"

cd "$HOME"
exec supermemory-server
