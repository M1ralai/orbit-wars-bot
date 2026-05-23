#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

ROOT_BEST="agents/versions/auto_v009_20260522_234815_auto_r0037_077_elite_auto_r0020_009_elite_auto_r0017_014_elite_auto_r0016_004_champion_template.py"
CW_BEST="families/counterwave/agents/versions/auto_v014_20260523_040214_auto_r0042_121_cw_champion_template.py"

echo "═══════════════════════════════════════════════"
echo "        Orbit Wars — Hybrid Evolution          "
echo "═══════════════════════════════════════════════"
echo "Training ML models on 728 unified historic games..."
echo "Opponents to defeat for promotion:"
echo " 1. Hybrid Champion"
echo " 2. Counterwave Best (v014)"
echo " 3. Root Best (v009)"
echo ""

exec "$PYTHON_BIN" families/hybrid/tools/auto_iterate.py \
  --continuous \
  --candidates-per-round 16 \
  --finalists 6 \
  --smoke-seeds 6 \
  --validation-seeds 30 \
  --workers 8 \
  --ml-ranker \
  --ml-min-samples 20 \
  --ml-min-games 10 \
  --ml-pool-size 512 \
  --ml-exploration-rate 0.20 \
  --ml-dataset-path training/ml_dataset.jsonl \
  --ml-model-path training/ml_ranker.joblib \
  --ml-priors-path training/adaptive_priors.json \
  --smoke-min-winrate 0.30 \
  --sleep-seconds 30 \
  --opponents champion "$CW_BEST" "$ROOT_BEST" \
  --min-winrate 0.54 \
  --min-opponent-winrate 0.53
