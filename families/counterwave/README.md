# Counterwave Family

Counterwave is a separate bot family with its own generated agents, versions,
training state, telemetry, and submission package.

It starts from the opposite posture of the current champion line:

- higher reserves and panic reserves
- lower neutral/production greed
- stronger short-hop enemy pressure
- threat-aware counterpunching
- limited attacks per turn instead of broad expansion

Important paths:

- `agents/versions/`: promoted Counterwave champions
- `runs/`: Counterwave round reports and candidates
- `training/`: Counterwave adaptive priors, elite pool, and ML ranker
- `telemetry/`: Counterwave match logs
- `state.json`: Counterwave loop state
- `submission.tar.gz`: Counterwave package only

Start a fresh loop:

```bash
./families/counterwave/run_loop.sh
```

The default loop starts with `--no-ml-ranker` so early Counterwave rounds build
their own validation history before any model starts selecting candidates.

The default opponent is the Counterwave family champion. At round zero that is
`agents/versions/v0_1.py`, so this line can evolve without touching the older
champion family.
