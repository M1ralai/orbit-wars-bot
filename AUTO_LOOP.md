# Orbit Wars Auto Loop

This repo now has two automation entry points:

```bash
.venv/bin/python tools/fetch_kaggle_replays.py --submission-id 52865334
```

Downloads completed Kaggle episodes for v0.1, replay JSON files, and accessible own-agent logs. A manifest is written to `replays/v0_1_manifest.json`.
Use `--submission-id latest` after future submits to sync the newest submission instead.

```bash
.venv/bin/python tools/replay_intake.py --download-missing
```

Builds `training/replay_examples.jsonl` and `training/replay_signals.json` from downloaded replay files.
Put external public episode ids, one per line, in `replays/external_episode_ids.txt`; the intake script will download any missing ones.
`tools/auto_iterate.py` automatically uses `training/replay_signals.json` when it exists.
The signal file now includes overall, early/mid/late, and enemy/neutral target profiles; round reports include `replay_signal`, `candidate_bases`, and `finalist_bases` so replay-derived candidates are auditable.

```bash
.venv/bin/python tools/auto_iterate.py --rounds 1
```

Runs one local search round:

1. Generate parameter-mutated agents under `auto_runs/`.
2. Smoke-test them against `v0_1`, `main`, and `production_hunter`.
3. Validate the top finalists on more seeds.
4. Gate all validated finalists.
5. If more than one finalist passes, run a seeded head-to-head playoff among them.
6. Promote only the playoff champion.
7. Rebuild `submission.py`, `submission_package/main.py`, and `submission.tar.gz`.

For an unattended overnight loop with Kaggle submission enabled:

```bash
.venv/bin/python tools/auto_iterate.py \
  --continuous \
  --candidates-per-round 16 \
  --finalists 8 \
  --smoke-seeds 6 \
  --validation-seeds 20 \
  --playoff-seeds 6 \
  --workers 4 \
  --sleep-seconds 0 \
  --submit \
  --max-submissions 3
```

The submit path is deliberately gated. By default it requires:

- combined validation winrate >= `0.62`
- every opponent winrate >= `0.54`
- `production_hunter` winrate >= `0.58`
- at least `60` validation games
- playoff champion when multiple finalists pass gates
- zero runtime errors
- at most one Kaggle submit per run
- 120 minutes between submits

On an M2 MacBook Air, start with `--workers 4`. Try `--workers 6` if thermals are fine; `8` can work but may throttle on long runs.

Useful outputs:

- `auto_runs/state.json`: current loop state and last promoted version
- `auto_runs/round_*/round_report.json`: per-round decision report
- `telemetry/auto/*.jsonl`: full local match telemetry
- `agents/versions/README.md`: promoted version notes

Active app automations:

- `orbit-wars-auto-iteration`: gated local search and optional submit.
- `orbit-wars-replay-intake`: replay sync plus training signal rebuild.
