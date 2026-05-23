"""Find the optimal worker count for this machine."""
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
    return seed


if __name__ == '__main__':
    N = 8  # matches per test
    print(f"Testing {N} matches with different worker counts...\n", flush=True)

    for workers in [1, 2, 3, 4, 6, 8]:
        t0 = time.perf_counter()
        if workers == 1:
            for s in range(N):
                job(s)
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futs = [pool.submit(job, s) for s in range(N)]
                [f.result() for f in as_completed(futs)]
        elapsed = time.perf_counter() - t0
        throughput = N / elapsed
        print(f"  {workers} workers: {elapsed:.1f}s total, {throughput:.2f} matches/sec, {elapsed/N:.1f}s/match", flush=True)
