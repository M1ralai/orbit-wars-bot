"""Test actual parallelism of ProcessPoolExecutor with kaggle matches."""
import time
import os
import sys
import logging
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, 'tools')
logging.getLogger('kaggle_environments').setLevel(50)
with open(os.devnull, 'w') as dn:
    with contextlib.redirect_stdout(dn), contextlib.redirect_stderr(dn):
        from tournament import run_match


def job(seed):
    r = run_match('main.py', 'main.py', seed, names=('a', 'b'))
    return seed, r['result']


if __name__ == '__main__':
    print("=== Parallelism diagnostic ===", flush=True)

    # How many CPU cores?
    cores = os.cpu_count()
    print(f"CPU cores available: {cores}", flush=True)

    # 1) Sequential baseline: 4 matches
    print("\n[1] Sequential: 4 matches...", flush=True)
    t0 = time.perf_counter()
    for s in range(4):
        job(s)
    seq4 = time.perf_counter() - t0
    per_match = seq4 / 4
    print(f"    {seq4:.1f}s total, {per_match:.1f}s/match", flush=True)

    # 2) Parallel 8 workers: 8 matches (should take ~1x per_match if fully parallel)
    print("\n[2] Parallel 8 workers: 8 matches...", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(job, s) for s in range(8)]
        for f in as_completed(futs):
            seed, result = f.result()
    par8 = time.perf_counter() - t0
    print(f"    {par8:.1f}s total, {par8/8:.1f}s/match", flush=True)
    print(f"    Effective parallelism: {seq4*2/par8:.1f}x (ideal=8x)", flush=True)

    # 3) Parallel 8 workers: 16 matches (should take ~2x per_match)
    print("\n[3] Parallel 8 workers: 16 matches...", flush=True)
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(job, s) for s in range(16)]
        for f in as_completed(futs):
            seed, result = f.result()
    par16 = time.perf_counter() - t0
    print(f"    {par16:.1f}s total, {par16/16:.1f}s/match", flush=True)
    print(f"    Effective parallelism: {seq4*4/par16:.1f}x (ideal=8x)", flush=True)

    # Summary
    print("\n=== Summary ===", flush=True)
    print(f"Single match cost: ~{per_match:.1f}s", flush=True)
    print(f"8-worker efficiency: {seq4*2/par8:.1f}x / 8x ideal = {seq4*2/par8/8:.0%}", flush=True)
    print(f"Full round estimate (192 matches, 8 workers): ~{192*per_match/min(8, seq4*2/par8):.0f}s = ~{192*per_match/min(8, seq4*2/par8)/60:.1f}min", flush=True)
