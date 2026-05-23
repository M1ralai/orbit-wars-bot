# Orbit Wars Agent Versions

## v0.1

Submitted to Kaggle as submission `52865334`.

- Source: `agents/main_v2.py`
- Kaggle public score: `618.6`
- Validation episode: `77246100`
- Public episodes: `77246468` win, `77246789` loss, `77247139` loss, `77247358` loss
- Strategy family: fast expansion
- Local validation:
  - `32/40` vs previous `main`
  - `24/40` vs `production_hunter`
- Validation logs: no stderr/runtime errors

## v0.2

Experimental local candidate.

- Source: `agents/versions/v0_2.py`
- Strategy family: fast expansion with mild enemy tempo pressure
- Goal: improve resilience against `production_hunter` without giving up the `v0.1` edge against old `main`
- Local result:
  - `11/20` vs `v0.1`
  - `15/20` vs previous `main`
  - `12/20` vs `production_hunter`
- Decision: hold, not submit. It slightly beats `v0.1` head-to-head, but regresses against `production_hunter`.

## auto_v001_20260521_000424_auto_r0003_011_gen_eco_light

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v001_20260521_000424_auto_r0003_011_gen_eco_light.py`
- Decision: passed
- Validation winrate: `0.625`
- Validation score: `0.765`
- Kaggle submission: `52866199`
- Kaggle public score: `600.0`
- Avg production delta: `13.8`
- Avg ship delta: `3494.9`
- Opponent breakdown:
  - `v0_1`: 0.625 (25/40)
  - `main`: 0.650 (26/40)
  - `production_hunter`: 0.600 (24/40)

## auto_v002_20260521_013440_manual_r0008_v3

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v002_20260521_013440_manual_r0008_v3.py`
- Decision: passed gate and won playoff from 2 entrants
- Validation winrate: `0.963`
- Validation score: `1.103`
- Avg production delta: `64.4`
- Avg ship delta: `3149.3`
- Opponent breakdown:
  - `champion:auto_v001_20260521_000424_auto_r0003_011_gen_eco_light`: 0.950 (38/40)
  - `v0_1`: 0.950 (38/40)
  - `main`: 1.000 (40/40)
  - `production_hunter`: 0.950 (38/40)

## auto_v003_20260521_021847_auto_r0011_010_replay_early

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v003_20260521_021847_auto_r0011_010_replay_early.py`
- Decision: passed gate and won playoff from 3 entrants
- Validation winrate: `0.950`
- Validation score: `1.090`
- Avg production delta: `64.8`
- Avg ship delta: `2710.6`
- Opponent breakdown:
  - `champion:auto_v002_20260521_013440_manual_r0008_v3`: 0.875 (35/40)
  - `v0_1`: 0.950 (38/40)
  - `main`: 1.000 (40/40)
  - `production_hunter`: 0.975 (39/40)

## auto_v004_20260521_023320_auto_r0012_003_champion_template

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v004_20260521_023320_auto_r0012_003_champion_template.py`
- Decision: passed gate and won playoff from 6 entrants
- Validation winrate: `0.919`
- Validation score: `1.059`
- Avg production delta: `56.5`
- Avg ship delta: `2221.2`
- Opponent breakdown:
  - `champion:auto_v002_20260521_013440_manual_r0008_v3`: 0.725 (29/40)
  - `v0_1`: 1.000 (40/40)
  - `main`: 1.000 (40/40)
  - `production_hunter`: 0.950 (38/40)

## auto_v005_20260521_024032_auto_r0013_008_champion_template

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v005_20260521_024032_auto_r0013_008_champion_template.py`
- Decision: passed gate and won playoff from 6 entrants
- Validation winrate: `0.900`
- Validation score: `1.040`
- Avg production delta: `61.5`
- Avg ship delta: `2804.8`
- Opponent breakdown:
  - `champion:auto_v002_20260521_013440_manual_r0008_v3`: 0.725 (29/40)
  - `v0_1`: 0.925 (37/40)
  - `main`: 1.000 (40/40)
  - `production_hunter`: 0.950 (38/40)

## auto_v006_20260522_221515_auto_r0022_015_elite_auto_r0013_008_champion_template

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v006_20260522_221515_auto_r0022_015_elite_auto_r0013_008_champion_template.py`
- Decision: passed gate and won playoff from 4 entrants
- Validation winrate: `0.955`
- Validation score: `1.095`
- Avg production delta: `67.9`
- Avg ship delta: `3422.1`
- Opponent breakdown:
  - `champion:auto_v002_20260521_013440_manual_r0008_v3`: 0.825 (33/40)
  - `v0_2`: 0.975 (39/40)
  - `v0_1`: 1.000 (40/40)
  - `main`: 1.000 (40/40)
  - `production_hunter`: 0.975 (39/40)

## auto_v007_20260522_224349_auto_r0025_010_elite_auto_r0018_008_champion_template

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v007_20260522_224349_auto_r0025_010_elite_auto_r0018_008_champion_template.py`
- Decision: passed gate; no playoff needed
- Validation winrate: `0.633`
- Validation score: `0.773`
- Avg production delta: `15.8`
- Avg ship delta: `512.0`
- Opponent breakdown:
  - `champion:auto_v006_20260522_221515_auto_r0022_015_elite_auto_r0013_008_champion_template`: 0.633 (38/60)

## auto_v008_20260522_234021_auto_r0035_473_champion_template

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v008_20260522_234021_auto_r0035_473_champion_template.py`
- Decision: passed gate; no playoff needed
- Validation winrate: `0.633`
- Validation score: `0.773`
- Avg production delta: `13.1`
- Avg ship delta: `652.7`
- Opponent breakdown:
  - `champion:auto_v007_20260522_224349_auto_r0025_010_elite_auto_r0018_008_champion_template`: 0.633 (38/60)

## auto_v009_20260522_234815_auto_r0037_077_elite_auto_r0020_009_elite_auto_r0017_014_elite_auto_r0016_004_champion_template

Auto-promoted local candidate.

- Source: `/Users/atahandemirer/Developer/orbit-wars-bot/agents/versions/auto_v009_20260522_234815_auto_r0037_077_elite_auto_r0020_009_elite_auto_r0017_014_elite_auto_r0016_004_champion_template.py`
- Decision: passed gate and won playoff from 2 entrants
- Validation winrate: `0.667`
- Validation score: `0.807`
- Avg production delta: `29.9`
- Avg ship delta: `966.4`
- Opponent breakdown:
  - `champion:auto_v008_20260522_234021_auto_r0035_473_champion_template`: 0.667 (40/60)
