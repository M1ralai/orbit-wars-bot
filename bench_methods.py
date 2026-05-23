"""Benchmark different match execution methods."""
import time
import os
import sys
import logging
import contextlib
import importlib.util
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, 'tools')
logging.getLogger('kaggle_environments').setLevel(50)
with open(os.devnull, 'w') as dn:
    with contextlib.redirect_stdout(dn), contextlib.redirect_stderr(dn):
        from kaggle_environments import make


def load_agent(path):
    spec = importlib.util.spec_from_file_location('_agent', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def run_match_file(seed):
    env = make('orbit_wars', configuration={'seed': seed}, debug=False)
    env.run(['main.py', 'main.py'])
    return env.steps[-1][0].reward > env.steps[-1][1].reward


def run_match_callable(args):
    seed, agent_a_path, agent_b_path = args
    a = load_agent(agent_a_path)
    b = load_agent(agent_b_path)
    env = make('orbit_wars', configuration={'seed': seed}, debug=False)
    env.run([a, b])
    return env.steps[-1][0].reward > env.steps[-1][1].reward


def run_match_cached(args):
    seed = args
    env = make('orbit_wars', configuration={'seed': seed}, debug=False)
    env.run([_cached_a, _cached_b])
    return env.steps[-1][0].reward > env.steps[-1][1].reward

_cached_a = None
_cached_b = None

def init_worker(a_path, b_path):
    global _cached_a, _cached_b
    _cached_a = load_agent(a_path)
    _cached_b = load_agent(b_path)


if __name__ == '__main__':
    N = 8
    WORKERS = 4

    # Method 1: Current approach - file paths
    print(f"[1] File paths, {WORKERS} workers, {N} matches...", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(run_match_file, range(N)))
    t_file = time.perf_counter() - t0
    print(f"    {t_file:.1f}s ({t_file/N:.2f}s/match, {N/t_file:.2f}/s)", flush=True)

    # Method 2: Load agent per-call in worker
    print(f"\n[2] Load callable per-call, {WORKERS} workers, {N} matches...", flush=True)
    t0 = time.perf_counter()
    jobs = [(s, 'main.py', 'main.py') for s in range(N)]
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(run_match_callable, jobs))
    t_callable = time.perf_counter() - t0
    print(f"    {t_callable:.1f}s ({t_callable/N:.2f}s/match, {N/t_callable:.2f}/s)", flush=True)

    # Method 3: Cache agent in worker process (load once per worker, not per match)
    print(f"\n[3] Cached callable (init once per worker), {WORKERS} workers, {N} matches...", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=WORKERS, initializer=init_worker, initargs=('main.py', 'main.py')) as pool:
        list(pool.map(run_match_cached, range(N)))
    t_cached = time.perf_counter() - t0
    print(f"    {t_cached:.1f}s ({t_cached/N:.2f}s/match, {N/t_cached:.2f}/s)", flush=True)

    # Method 4: Sequential callable baseline
    print(f"\n[4] Sequential callable baseline, {N} matches...", flush=True)
    a = load_agent('main.py')
    t0 = time.perf_counter()
    for s in range(N):
        env = make('orbit_wars', configuration={'seed': s}, debug=False)
        env.run([a, a])
    t_seq = time.perf_counter() - t0
    print(f"    {t_seq:.1f}s ({t_seq/N:.2f}s/match, {N/t_seq:.2f}/s)", flush=True)

    print(f"\n=== Summary ({N} matches, {WORKERS} workers) ===", flush=True)
    print(f"File paths (current):    {t_file:.1f}s  (baseline)", flush=True)
    print(f"Callable per-call:       {t_callable:.1f}s  ({t_file/t_callable:.2f}x)", flush=True)
    print(f"Cached callable:         {t_cached:.1f}s  ({t_file/t_cached:.2f}x)", flush=True)
    print(f"Sequential callable:     {t_seq:.1f}s", flush=True)
    print(f"\nProjected full smoke round (192 matches):", flush=True)
    print(f"  Current:   {192*t_file/N:.0f}s = {192*t_file/N/60:.1f}min", flush=True)
    print(f"  Optimized: {192*t_cached/N:.0f}s = {192*t_cached/N/60:.1f}min", flush=True)
