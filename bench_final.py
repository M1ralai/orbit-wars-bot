"""Final benchmark: old vs new run_match with parallel workers."""
import time
import sys
import os
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
    return r['result']


if __name__ == '__main__':
    N = 16
    W = 4

    print(f"=== {N} matches, {W} workers ===\n", flush=True)

    # Sequential
    t0 = time.perf_counter()
    for s in range(N):
        job(s)
    t_seq = time.perf_counter() - t0
    print(f"Sequential: {t_seq:.1f}s ({t_seq/N:.2f}s/match)", flush=True)

    # Parallel
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=W) as pool:
        futs = [pool.submit(job, s) for s in range(N)]
        [f.result() for f in as_completed(futs)]
    t_par = time.perf_counter() - t0
    print(f"Parallel:   {t_par:.1f}s ({t_par/N:.2f}s/match)", flush=True)

    print(f"\nParallel speedup: {t_seq/t_par:.2f}x", flush=True)
    print(f"\nProjected full smoke (192 matches, {W} workers): {192*t_par/N:.0f}s = {192*t_par/N/60:.1f}min", flush=True)
    print(f"Projected full round (576 matches, {W} workers): {576*t_par/N:.0f}s = {576*t_par/N/60:.1f}min", flush=True)
