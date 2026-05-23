#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" families/counterwave/tools/auto_iterate.py \
  --continuous \
  --candidates-per-round 16 \
  --finalists 8 \
  --smoke-seeds 6 \
  --validation-seeds 30 \
  --workers 8 \
  --ml-ranker \
  --ml-min-samples 20 \
  --ml-pool-size 512 \
  --ml-exploration-rate 0.20 \
  --sleep-seconds 30
