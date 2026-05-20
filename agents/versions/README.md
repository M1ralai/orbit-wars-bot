# Orbit Wars Agent Versions

## v0.1

Submitted to Kaggle as submission `52865334`.

- Source: `agents/main_v2.py`
- Kaggle public score: `600.0`
- Validation episode: `77246100`
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
