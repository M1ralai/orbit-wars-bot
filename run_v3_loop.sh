#!/bin/bash
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
VENV="$REPO/.venv/bin/python"

echo "═══════════════════════════════════════════════"
echo "  Orbit Wars — Auto-Iteration Loop (Optimus)   "
echo "═══════════════════════════════════════════════"

echo "Starting continuous auto-iteration loop..."
echo "       (Ctrl+C to stop — state is auto-saved)"
echo ""
exec $VENV "$REPO/tools/auto_iterate.py" \
    --continuous \
    --candidate-agent "v3=agents/v3_strategic.py" \
    --candidates-per-round 16 \
    --finalists 8 \
    --smoke-seeds 6 \
    --validation-seeds 20 \
    --playoff-seeds 6 \
    --workers 6 \
    --sleep-seconds 0 \
    --submit \
    --max-submissions 5 \
    --submit-cooldown-minutes 90 \
    --min-winrate 0.58 \
    --min-champion-winrate 0.50 \
    --min-production-hunter-winrate 0.54 \
    --opponents champion
