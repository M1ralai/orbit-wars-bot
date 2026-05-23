"""Test: reuse env, manual step loop, preloaded agents."""
import time
import os
import sys
import logging
import contextlib
import importlib.util

sys.path.insert(0, 'tools')
logging.getLogger('kaggle_environments').setLevel(50)
with open(os.devnull, 'w') as dn:
    with contextlib.redirect_stdout(dn), contextlib.redirect_stderr(dn):
        from kaggle_environments import make


def load_agent_fn(path):
    spec = importlib.util.spec_from_file_location('_a', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


if __name__ == '__main__':
    N = 8
    agent_a = load_agent_fn('main.py')
    agent_b = load_agent_fn('main.py')

    # Method 1: Current - make() + run() every time with file paths
    print(f"[1] make()+run(file,file) each match...", flush=True)
    t0 = time.perf_counter()
    for s in range(N):
        env = make('orbit_wars', configuration={'seed': s}, debug=False)
        env.run(['main.py', 'main.py'])
    t1 = time.perf_counter() - t0
    print(f"    {t1:.1f}s ({t1/N:.2f}s/match)", flush=True)

    # Method 2: make() each time but pass callable
    print(f"\n[2] make()+run(callable,callable) each match...", flush=True)
    t0 = time.perf_counter()
    for s in range(N):
        env = make('orbit_wars', configuration={'seed': s}, debug=False)
        env.run([agent_a, agent_b])
    t2 = time.perf_counter() - t0
    print(f"    {t2:.1f}s ({t2/N:.2f}s/match)", flush=True)

    # Method 3: Reuse env with reset + run callable
    print(f"\n[3] make() ONCE + reset()+run(callable) each match...", flush=True)
    env = make('orbit_wars', configuration={'seed': 0}, debug=False)
    t0 = time.perf_counter()
    for s in range(N):
        env.configuration.seed = s
        env.reset()
        env.run([agent_a, agent_b])
    t3 = time.perf_counter() - t0
    print(f"    {t3:.1f}s ({t3/N:.2f}s/match)", flush=True)

    # Method 4: Manual step loop (bypass env.run overhead)
    print(f"\n[4] make() ONCE + manual step loop...", flush=True)
    env = make('orbit_wars', configuration={'seed': 0}, debug=False)
    t0 = time.perf_counter()
    ok = 0
    for s in range(N):
        env.configuration.seed = s
        env.reset()
        while not env.done:
            actions = []
            for i, agent_state in enumerate(env.state):
                obs = agent_state.observation
                fn = agent_a if i == 0 else agent_b
                try:
                    action = fn(obs)
                except:
                    action = []
                actions.append(action)
            env.step(actions)
        ok += 1
    t4 = time.perf_counter() - t0
    print(f"    {t4:.1f}s ({t4/N:.2f}s/match) [{ok}/{N} ok]", flush=True)

    # Method 5: Manual step loop with dict obs (skip structify in agent call)
    print(f"\n[5] Manual step + dict observation (no structify)...", flush=True)
    env = make('orbit_wars', configuration={'seed': 0}, debug=False)
    t0 = time.perf_counter()
    ok = 0
    for s in range(N):
        env.configuration.seed = s
        env.reset()
        while not env.done:
            actions = []
            for i, agent_state in enumerate(env.state):
                obs = agent_state.observation
                # Convert Struct to dict if needed
                if hasattr(obs, '__dict__'):
                    obs_dict = dict(obs)
                else:
                    obs_dict = obs
                fn = agent_a if i == 0 else agent_b
                try:
                    action = fn(obs_dict)
                except:
                    action = []
                actions.append(action)
            env.step(actions)
        ok += 1
    t5 = time.perf_counter() - t0
    print(f"    {t5:.1f}s ({t5/N:.2f}s/match) [{ok}/{N} ok]", flush=True)

    print(f"\n{'='*50}", flush=True)
    print(f"[1] file+run:        {t1/N:.2f}s/match (baseline)", flush=True)
    print(f"[2] callable+run:    {t2/N:.2f}s/match ({t1/t2:.2f}x)", flush=True)
    print(f"[3] reuse+run:       {t3/N:.2f}s/match ({t1/t3:.2f}x)", flush=True)
    print(f"[4] manual step:     {t4/N:.2f}s/match ({t1/t4:.2f}x)", flush=True)
    print(f"[5] manual+dict:     {t5/N:.2f}s/match ({t1/t5:.2f}x)", flush=True)
    best = min(t2, t3, t4, t5)
    print(f"\nBest method saves {(t1-best)/t1:.0%} per match", flush=True)
    print(f"Projected 192 matches: {192*t1/N/4:.0f}s -> {192*best/N/4:.0f}s", flush=True)
