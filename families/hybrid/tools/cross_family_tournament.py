"""
Cross-Family Tournament: Root vs Counterwave
=============================================

Runs every root promoted version against every counterwave promoted version
in head-to-head matches (both sides, configurable seeds per matchup).

Output: a massive JSONL dataset written to families/hybrid/training/ml_dataset.jsonl
        containing param-level training rows the ML ranker can directly consume.

Each row captures:
  - candidate name, base family, params (translated to 26-param hybrid space)
  - games, wins, losses, winrate, score, quality
  - opponent info

Usage:
  python families/hybrid/tools/cross_family_tournament.py --seeds-per-matchup 20 --workers 8
"""

import argparse
import contextlib
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FAMILY_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = FAMILY_ROOT.parent.parent

# Import tournament engine
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
with open(os.devnull, "w", encoding="utf-8") as _devnull:
    with contextlib.redirect_stdout(_devnull), contextlib.redirect_stderr(_devnull):
        from tournament import run_match

# Directories
ROOT_VERSIONS = PROJECT_ROOT / "agents" / "versions"
CW_VERSIONS = PROJECT_ROOT / "families" / "counterwave" / "agents" / "versions"
OUTPUT_PATH = FAMILY_ROOT / "training" / "ml_dataset.jsonl"
TELEMETRY_PATH = FAMILY_ROOT / "telemetry" / "cross_family_tournament.jsonl"

# Translate root's 16-param space to 26-param hybrid space
ROOT_PARAM_DEFAULTS = {
    "panic_reserve_mult": 0.0,
    "neutral_tax": 0,
    "enemy_weak_bonus": 0.0,
    "counter_bonus": 0,
    "high_prod_tax": 0,
    "short_hop_bonus": 0.0,
    "short_hop_range": 16,
    "attack_fraction": 0.95,
    "max_attacks_per_turn": 8,
    "comet_bonus": 10,
}


def extract_params(agent_path):
    """Extract BASE_PARAMS dict from a generated agent file."""
    content = agent_path.read_text(encoding="utf-8")
    match = re.search(r"BASE_PARAMS\s*=\s*(\{.*?\})", content, re.DOTALL)
    if not match:
        return None
    try:
        params = eval(match.group(1))
        return params
    except Exception:
        return None


def translate_root_params(params):
    """Pad root 16-param dict to 26-param hybrid space."""
    translated = dict(params)
    for key, default in ROOT_PARAM_DEFAULTS.items():
        if key not in translated:
            translated[key] = default
    return translated


def discover_agents(versions_dir, family):
    """Find all promoted version .py files and extract their params."""
    agents = []
    if not versions_dir.exists():
        return agents

    for path in sorted(versions_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        params = extract_params(path)
        if params is None:
            continue

        if family == "root":
            params = translate_root_params(params)

        agents.append({
            "name": path.stem,
            "path": str(path),
            "family": family,
            "base": f"{family}_version",
            "params": params,
        })

    return agents


def run_match_job(job):
    """Run a single match and return the result with metadata."""
    record = run_match(
        job["agent_a"],
        job["agent_b"],
        job["seed"],
        names=(job["name_a"], job["name_b"]),
    )
    record.update(job["metadata"])
    return record


def build_jobs(root_agents, cw_agents, seeds_per_matchup, seed_start):
    """Build all match jobs: every root vs every cw, both sides."""
    jobs = []
    matchup_index = 0

    for root_agent in root_agents:
        for cw_agent in cw_agents:
            for seed_offset in range(seeds_per_matchup):
                seed = seed_start + matchup_index * seeds_per_matchup * 2 + seed_offset

                # Forward: root=A, cw=B
                jobs.append({
                    "agent_a": root_agent["path"],
                    "agent_b": cw_agent["path"],
                    "seed": seed,
                    "name_a": root_agent["name"],
                    "name_b": cw_agent["name"],
                    "metadata": {
                        "matchup": f"{root_agent['name']}_vs_{cw_agent['name']}",
                        "side": "forward",
                        "root_agent": root_agent["name"],
                        "cw_agent": cw_agent["name"],
                    },
                })

                # Reverse: cw=A, root=B
                jobs.append({
                    "agent_a": cw_agent["path"],
                    "agent_b": root_agent["path"],
                    "seed": seed + seeds_per_matchup,
                    "name_a": cw_agent["name"],
                    "name_b": root_agent["name"],
                    "metadata": {
                        "matchup": f"{root_agent['name']}_vs_{cw_agent['name']}",
                        "side": "reverse",
                        "root_agent": root_agent["name"],
                        "cw_agent": cw_agent["name"],
                    },
                })

            matchup_index += 1

    return jobs


def compute_summary(results):
    """Compute per-agent summaries from match results."""
    summaries = {}

    for record in results:
        result = record["result"]
        final = record.get("final", {})

        # Determine sides
        if record["side"] == "forward":
            root_side, cw_side = "0", "1"
            root_name = record["root_agent"]
            cw_name = record["cw_agent"]
        else:
            root_side, cw_side = "1", "0"
            root_name = record["root_agent"]
            cw_name = record["cw_agent"]

        # Update both agents
        for name, side, opponent_name in [
            (root_name, "a" if record["side"] == "forward" else "b", cw_name),
            (cw_name, "b" if record["side"] == "forward" else "a", root_name),
        ]:
            if name not in summaries:
                summaries[name] = {
                    "games": 0, "wins": 0, "losses": 0, "draws": 0, "errors": 0,
                    "production_delta": 0, "ship_delta": 0,
                    "by_opponent": {},
                }

            s = summaries[name]
            owner = "0" if side == "a" else "1"
            other = "1" if side == "a" else "0"

            s["games"] += 1
            s["production_delta"] += (
                final.get(owner, {}).get("production", 0)
                - final.get(other, {}).get("production", 0)
            )
            s["ship_delta"] += (
                final.get(owner, {}).get("total_ships", 0)
                - final.get(other, {}).get("total_ships", 0)
            )

            won = (side == "a" and result == "A_WIN") or (side == "b" and result == "B_WIN")
            lost = (side == "a" and result == "B_WIN") or (side == "b" and result == "A_WIN")

            if won:
                s["wins"] += 1
            elif lost:
                s["losses"] += 1
            elif result == "DRAW":
                s["draws"] += 1
            else:
                s["errors"] += 1

            # Per-opponent
            if opponent_name not in s["by_opponent"]:
                s["by_opponent"][opponent_name] = {"games": 0, "wins": 0, "losses": 0}
            opp = s["by_opponent"][opponent_name]
            opp["games"] += 1
            if won:
                opp["wins"] += 1
            elif lost:
                opp["losses"] += 1

    return summaries


def build_ml_rows(agents_by_name, summaries, min_games=10):
    """Convert summaries into ML training rows."""
    rows = []
    for agent_info in agents_by_name.values():
        name = agent_info["name"]
        summary = summaries.get(name)
        if not summary or summary["games"] < min_games:
            continue

        games = summary["games"]
        resolved = games - summary["errors"]
        if resolved == 0:
            continue

        winrate = summary["wins"] / resolved
        avg_prod = summary["production_delta"] / games
        avg_ship = summary["ship_delta"] / games
        prod_term = max(-0.08, min(0.08, avg_prod / 140.0))
        ship_term = max(-0.06, min(0.06, avg_ship / 900.0))
        error_term = -0.25 if summary["errors"] else 0.0
        score = winrate + prod_term + ship_term + error_term
        quality = winrate * 0.7 + score * 0.3

        rows.append({
            "round": 0,
            "round_dir": "cross_family_tournament",
            "candidate": name,
            "base": agent_info.get("base", "unknown"),
            "params": agent_info["params"],
            "games": games,
            "wins": summary["wins"],
            "losses": summary["losses"],
            "winrate": round(winrate, 4),
            "score": round(score, 4),
            "quality": round(quality, 4),
            "passed": winrate >= 0.54,
            "reason": "cross_family_tournament",
            "avg_production_delta": round(avg_prod, 2),
            "avg_ship_delta": round(avg_ship, 2),
            "source": "cross_family_tournament",
        })

    return rows


def main():
    parser = argparse.ArgumentParser(description="Cross-Family Tournament: Root vs Counterwave")
    parser.add_argument("--seeds-per-matchup", type=int, default=20,
                        help="Seeds per matchup (each played from both sides)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel match workers")
    parser.add_argument("--seed-start", type=int, default=100000,
                        help="Starting seed for matches")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH,
                        help="Output JSONL dataset path")
    parser.add_argument("--telemetry", type=Path, default=TELEMETRY_PATH,
                        help="Raw match telemetry output path")
    parser.add_argument("--append", action="store_true",
                        help="Append to existing dataset instead of overwriting")
    parser.add_argument("--min-games", type=int, default=10,
                        help="Minimum games per agent for inclusion in dataset")
    args = parser.parse_args()

    # Discover agents
    print("═══════════════════════════════════════════════")
    print("  Cross-Family Tournament: Root vs Counterwave ")
    print("═══════════════════════════════════════════════")

    root_agents = discover_agents(ROOT_VERSIONS, "root")
    cw_agents = discover_agents(CW_VERSIONS, "counterwave")

    print(f"\nDiscovered {len(root_agents)} root agents:")
    for a in root_agents:
        print(f"  • {a['name']}")
    print(f"\nDiscovered {len(cw_agents)} counterwave agents:")
    for a in cw_agents:
        print(f"  • {a['name']}")

    if not root_agents or not cw_agents:
        print("\nERROR: Need at least 1 agent from each family.")
        sys.exit(1)

    total_matchups = len(root_agents) * len(cw_agents)
    total_games = total_matchups * args.seeds_per_matchup * 2  # both sides
    print(f"\nMatchups: {total_matchups}")
    print(f"Seeds per matchup: {args.seeds_per_matchup} (x2 for both sides)")
    print(f"Total games: {total_games}")
    print(f"Workers: {args.workers}")
    print()

    # Build jobs
    jobs = build_jobs(root_agents, cw_agents, args.seeds_per_matchup, args.seed_start)

    # Run matches
    results = []
    args.telemetry.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    start_time = time.time()

    with args.telemetry.open("w", encoding="utf-8") as telem_file:
        if args.workers <= 1:
            for job in jobs:
                record = run_match_job(job)
                results.append(record)
                telem_file.write(json.dumps(record, sort_keys=True) + "\n")
                completed += 1
                if completed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (len(jobs) - completed) / rate if rate > 0 else 0
                    print(
                        f"  [{completed}/{len(jobs)}] "
                        f"{rate:.1f} games/s, ETA {eta:.0f}s",
                        flush=True,
                    )
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(run_match_job, job): job for job in jobs}
                for future in as_completed(futures):
                    record = future.result()
                    results.append(record)
                    telem_file.write(json.dumps(record, sort_keys=True) + "\n")
                    completed += 1
                    if completed % 20 == 0:
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        eta = (len(jobs) - completed) / rate if rate > 0 else 0
                        print(
                            f"  [{completed}/{len(jobs)}] "
                            f"{rate:.1f} games/s, ETA {eta:.0f}s",
                            flush=True,
                        )

    elapsed = time.time() - start_time
    print(f"\nAll {len(results)} games completed in {elapsed:.1f}s")

    # Compute summaries
    summaries = compute_summary(results)

    # Build agent lookup
    agents_by_name = {}
    for a in root_agents + cw_agents:
        agents_by_name[a["name"]] = a

    # Build ML rows
    ml_rows = build_ml_rows(agents_by_name, summaries, min_games=args.min_games)

    # Load existing data if appending
    existing_rows = []
    if args.append and args.output.exists():
        with args.output.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    existing_rows.append(json.loads(line))
        print(f"Loaded {len(existing_rows)} existing rows for append.")

    # Write output
    all_rows = existing_rows + ml_rows
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    print(f"\nML Dataset: {len(ml_rows)} new rows + {len(existing_rows)} existing = {len(all_rows)} total")
    print(f"Written to: {args.output}")

    # Print leaderboard
    print("\n═══════════════════════════════════════════════")
    print("  LEADERBOARD                                  ")
    print("═══════════════════════════════════════════════")

    leaderboard = []
    for row in ml_rows:
        leaderboard.append((row["candidate"], row["winrate"], row["score"], row["games"], row.get("base", "")))

    leaderboard.sort(key=lambda x: x[2], reverse=True)
    print(f"{'Rank':>4}  {'Agent':<60}  {'WR':>6}  {'Score':>6}  {'Games':>5}  {'Family'}")
    print("-" * 100)
    for i, (name, wr, score, games, base) in enumerate(leaderboard, 1):
        family = "ROOT" if "root" in base else "CW" if "counterwave" in base else "?"
        print(f"{i:>4}  {name:<60}  {wr:.3f}  {score:.3f}  {games:>5}  {family}")


if __name__ == "__main__":
    main()
