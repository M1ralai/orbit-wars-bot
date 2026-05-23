"""Test remaining optimization patches."""
import time
import sys
import os
import logging
import contextlib
import multiprocessing as mp

sys.path.insert(0, 'tools')
logging.getLogger('kaggle_environments').setLevel(50)
with open(os.devnull, 'w') as dn:
    with contextlib.redirect_stdout(dn), contextlib.redirect_stderr(dn):
        from tournament import run_match


def job(seed):
    r = run_match('main.py', 'main.py', seed, names=('a', 'b'))
    return r['result']


def job_chunked(seeds):
    return [job(s) for s in seeds]


def run_pool_test(label, method, N, W):
    from concurrent.futures import ProcessPoolExecutor, as_completed
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=W) as pool:
        if method == 'submit':
            futs = [pool.submit(job, s) for s in range(N)]
            [f.result() for f in as_completed(futs)]
        elif method == 'map':
            list(pool.map(job, range(N)))
        elif method == 'map_chunk':
            list(pool.map(job, range(N), chunksize=4))
    elapsed = time.perf_counter() - t0
    print(f"  {label}: {elapsed:.1f}s ({elapsed/N:.2f}s/match)", flush=True)
    return elapsed


if __name__ == '__main__':
    N = 16
    W = 4

    # === Test 1: Current start method ===
    print(f"Current mp start method: {mp.get_start_method()}", flush=True)
    print(f"\n=== Test 1: submit vs map vs map+chunksize ({N} matches, {W} workers) ===", flush=True)
    t_submit = run_pool_test("as_completed(submit)", "submit", N, W)
    t_map = run_pool_test("pool.map", "map", N, W)
    t_chunk = run_pool_test("pool.map chunk=4", "map_chunk", N, W)

    # === Test 2: fork vs spawn ===
    print(f"\n=== Test 2: fork vs spawn ===", flush=True)

    # spawn (current default on mac)
    print(f"  Testing spawn...", flush=True)
    mp.set_start_method("spawn", force=True)
    t_spawn = run_pool_test("spawn", "submit", N, W)

    # fork
    print(f"  Testing fork...", flush=True)
    try:
        mp.set_start_method("fork", force=True)
        t_fork = run_pool_test("fork", "submit", N, W)
    except Exception as e:
        print(f"  fork FAILED: {e}", flush=True)
        t_fork = None

    # forkserver
    print(f"  Testing forkserver...", flush=True)
    try:
        mp.set_start_method("forkserver", force=True)
        t_forkserver = run_pool_test("forkserver", "submit", N, W)
    except Exception as e:
        print(f"  forkserver FAILED: {e}", flush=True)
        t_forkserver = None

    # === Test 3: logging fully disabled ===
    print(f"\n=== Test 3: logging disabled ===", flush=True)
    logging.disable(logging.CRITICAL)
    mp.set_start_method("spawn", force=True)
    t_nolog = run_pool_test("logging disabled", "submit", N, W)
    logging.disable(logging.NOTSET)

    # === Summary ===
    print(f"\n{'='*50}", flush=True)
    print(f"Baseline (submit/spawn): {t_submit:.1f}s", flush=True)
    print(f"pool.map:                {t_map:.1f}s ({t_submit/t_map:.2f}x)", flush=True)
    print(f"pool.map chunk=4:        {t_chunk:.1f}s ({t_submit/t_chunk:.2f}x)", flush=True)
    if t_fork:
        print(f"fork:                    {t_fork:.1f}s ({t_submit/t_fork:.2f}x)", flush=True)
    if t_forkserver:
        print(f"forkserver:              {t_forkserver:.1f}s ({t_submit/t_forkserver:.2f}x)", flush=True)
    print(f"logging disabled:        {t_nolog:.1f}s ({t_submit/t_nolog:.2f}x)", flush=True)
