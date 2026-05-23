"""Benchmark: old vs new evaluate_candidates & playoff performance."""
import json
import os
import sys
import time
import tempfile
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ProcessPoolExecutor, as_completed

# Setup paths like the real script does
SCRIPT_DIR = Path(__file__).resolve().parent
FAMILY_ROOT = SCRIPT_DIR / "families" / "hybrid"
PROJECT_ROOT = SCRIPT_DIR
sys.path.insert(0, str(FAMILY_ROOT / "tools"))
sys.path.append(str(PROJECT_ROOT / "tools"))

os.chdir(str(SCRIPT_DIR))

from tournament import run_match  # noqa

# ── Configuration matching run_loop.sh ──
WORKERS = 8
NUM_CANDIDATES = 16
SMOKE_SEEDS = 6
OPPONENTS = ["champion"]
STATE_PATH = Path("families/hybrid/state.json")
CHAMPION_PATH = str(FAMILY_ROOT / "agents" / "versions" / "hybrid_genesis_v000.py")

# Use the first real candidate as all "candidates" for benchmarking
CANDIDATE_DIR = FAMILY_ROOT / "runs" / "lineage" / "round_0001_20260523_135409" / "candidates"
candidate_files = sorted(CANDIDATE_DIR.glob("*.py"))[:NUM_CANDIDATES]
if len(candidate_files) < NUM_CANDIDATES:
    # Pad by repeating
    while len(candidate_files) < NUM_CANDIDATES:
        candidate_files.append(candidate_files[0])

CANDIDATES = [
    {"name": f"bench_candidate_{i:03d}", "path": str(f), "base": "bench", "params": {}}
    for i, f in enumerate(candidate_files)
]

SEEDS = list(range(10000, 10000 + SMOKE_SEEDS))


def run_match_job(job):
    record = run_match(
        job["agent_a"], job["agent_b"], job["seed"],
        names=(job["name_a"], job["name_b"]),
    )
    record.update(job["metadata"])
    return record


# ══════════════════════════════════════════════
#  OLD VERSION: per-candidate pool + per-seed resolve
# ══════════════════════════════════════════════
def old_resolve_agent(agent, state_path):
    """Original: reads state.json from disk every call."""
    if agent == "champion":
        path = Path(state_path)
        if not path.is_absolute():
            path = FAMILY_ROOT / path
        for _ in range(3):
            try:
                if path.exists():
                    state = json.loads(path.read_text(encoding="utf-8"))
                    best = state.get("best_version_path")
                    if best and Path(best).exists():
                        return best
            except json.JSONDecodeError:
                time.sleep(0.05)
    return CHAMPION_PATH


def old_iter_job_results(jobs, workers):
    if workers <= 1:
        for job in jobs:
            yield run_match_job(job)
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_match_job, job) for job in jobs]
        for future in as_completed(futures):
            yield future.result()


def old_evaluate_candidates(candidates, opponents, seeds, telemetry_path, workers):
    """OLD: one pool per candidate, resolve_agent per seed."""
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    results_count = 0
    with telemetry_path.open("w", encoding="utf-8") as f:
        for candidate in candidates:
            jobs = []
            for opponent in opponents:
                for seed in seeds:
                    opponent_path = old_resolve_agent(opponent, "state.json")
                    opponent_name = f"champion:{Path(opponent_path).stem}"
                    jobs.append({
                        "agent_a": candidate["path"],
                        "agent_b": opponent_path,
                        "seed": seed,
                        "name_a": candidate["name"],
                        "name_b": opponent_name,
                        "metadata": {"candidate": candidate["name"], "opponent": opponent_name, "candidate_side": "a"},
                    })
                    jobs.append({
                        "agent_a": opponent_path,
                        "agent_b": candidate["path"],
                        "seed": seed,
                        "name_a": opponent_name,
                        "name_b": candidate["name"],
                        "metadata": {"candidate": candidate["name"], "opponent": opponent_name, "candidate_side": "b"},
                    })
            for record in old_iter_job_results(jobs, workers):
                f.write(json.dumps(record, sort_keys=True) + "\n")
                results_count += 1
    return results_count


# ══════════════════════════════════════════════
#  NEW VERSION: single pool + resolve once
# ══════════════════════════════════════════════
def new_resolve_opponents_once(opponents):
    """NEW: resolve all opponents once."""
    resolved = []
    for opponent in opponents:
        if opponent == "champion":
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            best = state.get("best_version_path")
            opponent_path = best if best and Path(best).exists() else CHAMPION_PATH
        else:
            opponent_path = CHAMPION_PATH
        opponent_name = f"champion:{Path(opponent_path).stem}"
        resolved.append((opponent, opponent_path, opponent_name))
    return resolved


def new_iter_job_results(jobs, workers):
    if workers <= 1:
        for job in jobs:
            yield run_match_job(job)
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_match_job, job) for job in jobs]
        for future in as_completed(futures):
            yield future.result()


def new_evaluate_candidates(candidates, opponents, seeds, telemetry_path, workers):
    """NEW: single pool, resolve once."""
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_opponents = new_resolve_opponents_once(opponents)
    all_jobs = []
    for candidate in candidates:
        for _, opponent_path, opponent_name in resolved_opponents:
            for seed in seeds:
                all_jobs.append({
                    "agent_a": candidate["path"],
                    "agent_b": opponent_path,
                    "seed": seed,
                    "name_a": candidate["name"],
                    "name_b": opponent_name,
                    "metadata": {"candidate": candidate["name"], "opponent": opponent_name, "candidate_side": "a"},
                })
                all_jobs.append({
                    "agent_a": opponent_path,
                    "agent_b": candidate["path"],
                    "seed": seed,
                    "name_a": opponent_name,
                    "name_b": candidate["name"],
                    "metadata": {"candidate": candidate["name"], "opponent": opponent_name, "candidate_side": "b"},
                })

    results_count = 0
    with telemetry_path.open("w", encoding="utf-8") as f:
        for record in new_iter_job_results(all_jobs, workers):
            f.write(json.dumps(record, sort_keys=True) + "\n")
            results_count += 1
    return results_count


# ══════════════════════════════════════════════
#  OVERHEAD-ONLY BENCHMARK (no actual matches)
# ══════════════════════════════════════════════
def bench_overhead_old(candidates, opponents, seeds):
    """Measure just the overhead: resolve_agent calls + pool creation/teardown (no actual matches)."""
    pool_creates = 0
    resolve_calls = 0
    for candidate in candidates:
        jobs = []
        for opponent in opponents:
            for seed in seeds:
                old_resolve_agent(opponent, "state.json")
                resolve_calls += 1
                old_resolve_agent(opponent, "state.json")
                resolve_calls += 1
        # Simulate pool create/destroy
        pool_creates += 1
    return pool_creates, resolve_calls


def bench_overhead_new(candidates, opponents, seeds):
    """Measure just the overhead: resolve once + single pool."""
    resolve_calls = 0
    resolved = new_resolve_opponents_once(opponents)
    resolve_calls = len(opponents)  # once
    pool_creates = 1
    return pool_creates, resolve_calls


# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print(f"Benchmark: {NUM_CANDIDATES} candidates, {SMOKE_SEEDS} seeds, {WORKERS} workers")
    print(f"Total matches per version: {NUM_CANDIDATES * len(OPPONENTS) * SMOKE_SEEDS * 2}")
    print("=" * 60)

    # 1) Overhead-only benchmark
    print("\n── Overhead-only benchmark (no matches) ──")

    t0 = time.perf_counter()
    for _ in range(100):
        old_pools, old_resolves = bench_overhead_old(CANDIDATES, OPPONENTS, SEEDS)
    old_overhead = (time.perf_counter() - t0) / 100

    t0 = time.perf_counter()
    for _ in range(100):
        new_pools, new_resolves = bench_overhead_new(CANDIDATES, OPPONENTS, SEEDS)
    new_overhead = (time.perf_counter() - t0) / 100

    print(f"OLD: {old_pools} pool creates, {old_resolves} resolve_agent calls, {old_overhead*1000:.2f}ms avg")
    print(f"NEW: {new_pools} pool creates, {new_resolves} resolve_agent calls, {new_overhead*1000:.2f}ms avg")
    print(f"Overhead speedup: {old_overhead/new_overhead:.1f}x")

    # 2) Pool startup/teardown benchmark
    print("\n── Pool startup/teardown benchmark ──")

    def noop_job(_):
        return 0

    t0 = time.perf_counter()
    for _ in range(NUM_CANDIDATES):
        with ProcessPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(noop_job, range(4)))
    old_pool_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        for _ in range(NUM_CANDIDATES):
            list(pool.map(noop_job, range(4)))
    new_pool_time = time.perf_counter() - t0

    print(f"OLD ({NUM_CANDIDATES} pools): {old_pool_time:.3f}s")
    print(f"NEW (1 pool):  {new_pool_time:.3f}s")
    print(f"Pool overhead saved: {old_pool_time - new_pool_time:.3f}s ({old_pool_time/new_pool_time:.1f}x)")

    # 3) Full end-to-end with real matches (reduced set)
    BENCH_CANDIDATES = CANDIDATES[:4]  # Use 4 candidates to keep it reasonable
    BENCH_SEEDS = SEEDS[:2]  # 2 seeds
    total_matches = len(BENCH_CANDIDATES) * len(OPPONENTS) * len(BENCH_SEEDS) * 2
    print(f"\n── Full E2E benchmark ({len(BENCH_CANDIDATES)} candidates, {len(BENCH_SEEDS)} seeds, {total_matches} matches) ──")

    with tempfile.TemporaryDirectory() as tmpdir:
        old_path = Path(tmpdir) / "old_telemetry.jsonl"
        t0 = time.perf_counter()
        old_count = old_evaluate_candidates(BENCH_CANDIDATES, OPPONENTS, BENCH_SEEDS, old_path, WORKERS)
        old_e2e = time.perf_counter() - t0
        print(f"OLD: {old_e2e:.2f}s ({old_count} results)")

        new_path = Path(tmpdir) / "new_telemetry.jsonl"
        t0 = time.perf_counter()
        new_count = new_evaluate_candidates(BENCH_CANDIDATES, OPPONENTS, BENCH_SEEDS, new_path, WORKERS)
        new_e2e = time.perf_counter() - t0
        print(f"NEW: {new_e2e:.2f}s ({new_count} results)")

        print(f"E2E speedup: {old_e2e/new_e2e:.2f}x (saved {old_e2e - new_e2e:.2f}s)")
        print(f"Projected full round savings ({NUM_CANDIDATES} candidates, {SMOKE_SEEDS} seeds): ~{(old_e2e - new_e2e) * (NUM_CANDIDATES/len(BENCH_CANDIDATES)) * (SMOKE_SEEDS/len(BENCH_SEEDS)):.1f}s")
