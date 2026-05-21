import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_agents import CANDIDATES, TEMPLATE  # noqa: E402
from tournament import AGENTS, run_match  # noqa: E402


DEFAULT_OPPONENTS = ["champion", "v0_1", "main", "production_hunter"]
DEFAULT_COMPETITION = "orbit-wars"

INT_PARAMS = {
    "min_ships",
    "min_reserve",
    "neutral_bonus",
    "enemy_bonus",
    "pressure_max",
    "pressure_divisor",
    "production_weight",
    "high_production_weight",
    "overkill",
    "high_prod_extra",
    "enemy_extra",
}

PARAM_BOUNDS = {
    "min_ships": (6, 18),
    "min_reserve": (2, 10),
    "reserve_prod_mult": (1.8, 4.4),
    "neutral_bonus": (0, 28),
    "enemy_bonus": (4, 48),
    "pressure_max": (0, 36),
    "pressure_divisor": (10, 80),
    "production_weight": (24, 48),
    "high_production_weight": (32, 70),
    "distance_weight": (1.35, 2.65),
    "high_distance_weight": (1.1, 2.3),
    "ship_weight": (0.75, 1.75),
    "high_ship_weight": (0.7, 1.55),
    "overkill": (1, 5),
    "high_prod_extra": (0, 3),
    "enemy_extra": (0, 8),
}


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def load_state(path):
    if not path.exists():
        return {"round": 0, "promotions": 0, "submissions": 0}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def clamp(name, value):
    low, high = PARAM_BOUNDS[name]
    value = max(low, min(high, value))
    if name in INT_PARAMS:
        return int(round(value))
    return round(float(value), 4)


def mutate_params(base, rng):
    params = dict(base)
    
    # Remove keys not in PARAM_BOUNDS (like 'source')
    for k in list(params.keys()):
        if k not in PARAM_BOUNDS:
            del params[k]
            
    # Fill in any missing keys with defaults from PARAM_BOUNDS
    for k, (low, high) in PARAM_BOUNDS.items():
        if k not in params:
            if k in INT_PARAMS:
                params[k] = int(round((low + high) / 2))
            else:
                params[k] = round(float((low + high) / 2), 4)

    for name, value in list(params.items()):
        if rng.random() > 0.72:
            continue

        low, high = PARAM_BOUNDS[name]
        span = high - low
        if name in INT_PARAMS:
            delta = rng.choice([-3, -2, -1, 1, 2, 3])
            if rng.random() < 0.2:
                delta *= 2
            params[name] = clamp(name, value + delta)
        else:
            delta = rng.uniform(-0.12, 0.12) * span
            params[name] = clamp(name, value + delta)

    for name in rng.sample(list(params), k=rng.randint(1, 3)):
        low, high = PARAM_BOUNDS[name]
        if name in INT_PARAMS:
            params[name] = int(rng.randint(int(low), int(high)))
        else:
            params[name] = round(rng.uniform(low, high), 4)

    if params["high_production_weight"] < params["production_weight"]:
        params["high_production_weight"] = params["production_weight"]
    if params["high_distance_weight"] > params["distance_weight"]:
        params["high_distance_weight"] = params["distance_weight"]
    if params["high_ship_weight"] > params["ship_weight"]:
        params["high_ship_weight"] = params["ship_weight"]

    return {name: clamp(name, value) for name, value in params.items()}


def write_candidate(name, params, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.py"
    path.write_text(TEMPLATE.format(**params), encoding="utf-8")
    return path


def params_from_replay_profile(signals, profile, label):
    params = dict(CANDIDATES["gen_fast_expand"])
    owner_rates = profile.get("target_owner_rates", {})
    ship_ratio = (profile.get("source_ship_ratio") or {}).get("avg") or 0.4
    high_prod_rate = profile.get("high_production_target_rate", 0.0)
    distance_avg = (profile.get("target_distance") or {}).get("avg") or 30.0

    params["enemy_bonus"] = clamp(
        "enemy_bonus",
        params["enemy_bonus"] + owner_rates.get("enemy", 0.0) * 30,
    )
    params["neutral_bonus"] = clamp(
        "neutral_bonus",
        params["neutral_bonus"] + owner_rates.get("neutral", 0.0) * 18,
    )
    params["high_production_weight"] = clamp(
        "high_production_weight",
        params["high_production_weight"] + high_prod_rate * 18,
    )
    params["production_weight"] = clamp(
        "production_weight",
        params["production_weight"] + high_prod_rate * 8,
    )
    params["reserve_prod_mult"] = clamp(
        "reserve_prod_mult",
        params["reserve_prod_mult"] - max(0.0, ship_ratio - 0.45) * 1.5,
    )
    params["min_ships"] = clamp(
        "min_ships",
        params["min_ships"] - max(0.0, ship_ratio - 0.45) * 6,
    )
    params["distance_weight"] = clamp(
        "distance_weight",
        params["distance_weight"] + (distance_avg - 32.0) / 80.0,
    )
    params["high_distance_weight"] = min(
        params["distance_weight"],
        clamp(
            "high_distance_weight",
            params["high_distance_weight"] + (distance_avg - 32.0) / 100.0,
        ),
    )

    if "enemy" in label:
        params["enemy_bonus"] = clamp("enemy_bonus", params["enemy_bonus"] + 8)
        params["pressure_max"] = clamp("pressure_max", params["pressure_max"] + 8)
        params["enemy_extra"] = clamp("enemy_extra", params["enemy_extra"] + 1)
    if "neutral" in label or "early" in label:
        params["neutral_bonus"] = clamp("neutral_bonus", params["neutral_bonus"] + 8)
        params["min_ships"] = clamp("min_ships", params["min_ships"] - 2)
        params["reserve_prod_mult"] = clamp(
            "reserve_prod_mult",
            params["reserve_prod_mult"] - 0.25,
        )
    if "late" in label:
        params["enemy_bonus"] = clamp("enemy_bonus", params["enemy_bonus"] + 12)
        params["neutral_bonus"] = clamp("neutral_bonus", params["neutral_bonus"] - 4)
        params["pressure_max"] = clamp("pressure_max", params["pressure_max"] + 14)

    return params


def load_replay_base(path):
    path = REPO_ROOT / path
    if not path.exists():
        return [], {}

    signals = json.loads(path.read_text(encoding="utf-8"))
    if signals.get("examples", 0) < 20:
        return [], signals

    bases = [("replay_signal_overall", params_from_replay_profile(signals, signals, "overall"))]
    phase_profiles = signals.get("phase_profiles", {})
    target_profiles = signals.get("target_profiles", {})

    for phase, profile in phase_profiles.items():
        if profile.get("examples", 0) >= 20:
            bases.append(
                (
                    f"replay_{phase}",
                    params_from_replay_profile(signals, profile, phase),
                )
            )

    for target, profile in target_profiles.items():
        if target in ("enemy", "neutral") and profile.get("examples", 0) >= 20:
            bases.append(
                (
                    f"replay_target_{target}",
                    params_from_replay_profile(signals, profile, target),
                )
            )

    return bases, signals


def generate_round_candidates(round_index, count, output_dir, rng, base_items):
    records = []
    for candidate_index in range(count):
        base_name, base_params = rng.choice(base_items)
        params = mutate_params(base_params, rng)
        name = f"auto_r{round_index:04d}_{candidate_index:03d}_{base_name}"
        path = write_candidate(name, params, output_dir)
        records.append(
            {
                "name": name,
                "path": str(path),
                "base": base_name,
                "params": params,
            }
        )
    return records


def load_candidate_agents(specs, round_index):
    candidates = []
    for spec in specs:
        try:
            name, path = spec.split("=", 1)
        except ValueError as exc:
            raise SystemExit(f"invalid candidate agent {spec!r}; expected NAME=PATH") from exc

        name = name.strip()
        path = Path(path.strip())
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not name or not path.exists():
            raise SystemExit(f"invalid candidate agent {spec!r}; missing name or path")

        candidates.append(
            {
                "name": f"manual_r{round_index:04d}_{name}",
                "path": str(path),
                "base": "manual",
                "params": {"source": str(path)},
            }
        )

    return candidates


def read_state_for_champion(path):
    path = REPO_ROOT / path
    for _ in range(3):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            time.sleep(0.05)
    return {}


def champion_path_from_state(state):
    candidates = [
        state.get("last_submitted_version_path"),
        state.get("submitted_version_path"),
    ]

    if int(state.get("submissions", 0)) > 0:
        candidates.append(state.get("best_version_path"))

    candidates.extend(
        [
            str(REPO_ROOT / "submission_package" / "main.py"),
            str(REPO_ROOT / "agents" / "versions" / "v0_1.py"),
        ]
    )

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))

    raise SystemExit("could not resolve champion path")


def resolve_agent(agent, state_path=None):
    if agent in ("champion", "latest", "last_submitted"):
        return champion_path_from_state(read_state_for_champion(state_path))
    if agent in AGENTS:
        return AGENTS[agent]
    path = Path(agent)
    if not path.exists():
        raise SystemExit(f"unknown opponent or missing agent path: {agent}")
    return str(path)


def opponent_label(agent, path):
    if agent in ("champion", "latest", "last_submitted"):
        return f"champion:{Path(path).stem}"
    return agent


def new_summary(name):
    return {
        "name": name,
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "errors": 0,
        "production_delta": 0,
        "ship_delta": 0,
        "loss_seeds": [],
        "error_seeds": [],
        "by_opponent": {},
    }


def side_won(result, side):
    return (side == "a" and result == "A_WIN") or (side == "b" and result == "B_WIN")


def side_lost(result, side):
    return (side == "a" and result == "B_WIN") or (side == "b" and result == "A_WIN")


def add_result(summary, record, side, opponent):
    final = record.get("final", {})
    owner = "0" if side == "a" else "1"
    other = "1" if side == "a" else "0"
    opponent_summary = summary["by_opponent"].setdefault(opponent, new_summary(opponent))

    for target in (summary, opponent_summary):
        target["games"] += 1
        target["production_delta"] += (
            final.get(owner, {}).get("production", 0)
            - final.get(other, {}).get("production", 0)
        )
        target["ship_delta"] += (
            final.get(owner, {}).get("total_ships", 0)
            - final.get(other, {}).get("total_ships", 0)
        )

        if side_won(record["result"], side):
            target["wins"] += 1
        elif side_lost(record["result"], side):
            target["losses"] += 1
            target["loss_seeds"].append(record["seed"])
        elif record["result"] == "DRAW":
            target["draws"] += 1
        else:
            target["errors"] += 1
            target["error_seeds"].append(record["seed"])


def winrate(summary):
    resolved = summary["games"] - summary["errors"]
    return summary["wins"] / resolved if resolved else 0.0


def avg(summary, field):
    return summary[field] / summary["games"] if summary["games"] else 0.0


def score_summary(summary):
    production_term = max(-0.08, min(0.08, avg(summary, "production_delta") / 140.0))
    ship_term = max(-0.06, min(0.06, avg(summary, "ship_delta") / 900.0))
    error_term = -0.25 if summary["errors"] else 0.0
    return winrate(summary) + production_term + ship_term + error_term


def compact_summary(summary):
    return {
        "games": summary["games"],
        "wins": summary["wins"],
        "losses": summary["losses"],
        "draws": summary["draws"],
        "errors": summary["errors"],
        "winrate": round(winrate(summary), 4),
        "score": round(score_summary(summary), 4),
        "avg_production_delta": round(avg(summary, "production_delta"), 2),
        "avg_ship_delta": round(avg(summary, "ship_delta"), 2),
        "loss_seeds": summary["loss_seeds"][:12],
        "error_seeds": summary["error_seeds"][:12],
        "by_opponent": {
            opponent: {
                "games": data["games"],
                "wins": data["wins"],
                "losses": data["losses"],
                "errors": data["errors"],
                "winrate": round(winrate(data), 4),
                "avg_production_delta": round(avg(data, "production_delta"), 2),
                "avg_ship_delta": round(avg(data, "ship_delta"), 2),
            }
            for opponent, data in summary["by_opponent"].items()
        },
    }


def candidate_rollup(candidates):
    counts = {}
    for candidate in candidates:
        base = candidate.get("base", "unknown")
        counts[base] = counts.get(base, 0) + 1
    return dict(sorted(counts.items()))


def run_match_job(job):
    record = run_match(
        job["agent_a"],
        job["agent_b"],
        job["seed"],
        names=(job["name_a"], job["name_b"]),
    )
    record.update(job["metadata"])
    return record


def iter_job_results(jobs, workers):
    if workers <= 1:
        for job in jobs:
            yield run_match_job(job)
        return

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(run_match_job, job) for job in jobs]
        for future in as_completed(futures):
            yield future.result()


def evaluate_candidate(candidate, opponents, seeds, telemetry_file, args):
    summary = new_summary(candidate["name"])
    candidate_path = candidate["path"]
    jobs = []

    for opponent in opponents:
        for seed in seeds:
            opponent_path = resolve_agent(opponent, args.state)
            opponent_name = opponent_label(opponent, opponent_path)
            jobs.append(
                {
                    "agent_a": candidate_path,
                    "agent_b": opponent_path,
                    "seed": seed,
                    "name_a": candidate["name"],
                    "name_b": opponent_name,
                    "metadata": {
                        "candidate": candidate["name"],
                        "opponent": opponent_name,
                        "opponent_alias": opponent,
                        "opponent_path": opponent_path,
                        "candidate_side": "a",
                    },
                }
            )

            jobs.append(
                {
                    "agent_a": opponent_path,
                    "agent_b": candidate_path,
                    "seed": seed,
                    "name_a": opponent_name,
                    "name_b": candidate["name"],
                    "metadata": {
                        "candidate": candidate["name"],
                        "opponent": opponent_name,
                        "opponent_alias": opponent,
                        "opponent_path": opponent_path,
                        "candidate_side": "b",
                    },
                }
            )

    for record in iter_job_results(jobs, args.workers):
        add_result(summary, record, record["candidate_side"], record["opponent"])
        telemetry_file.write(json.dumps(record, sort_keys=True) + "\n")

    return summary


def evaluate_candidates(candidates, opponents, seeds, telemetry_path, args):
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    summaries = {}
    with telemetry_path.open("w", encoding="utf-8") as telemetry_file:
        for candidate in candidates:
            summary = evaluate_candidate(candidate, opponents, seeds, telemetry_file, args)
            summaries[candidate["name"]] = summary
            print(
                f"{candidate['name']}: winrate={winrate(summary):.3f} "
                f"score={score_summary(summary):.3f} games={summary['games']}",
                flush=True,
            )
    return summaries


def rank_candidates(candidates, summaries):
    return sorted(
        candidates,
        key=lambda candidate: score_summary(summaries[candidate["name"]]),
        reverse=True,
    )


def passes_gate(summary, args):
    if summary["games"] < args.min_validation_games:
        return False, f"validation games below {args.min_validation_games}"
    if summary["errors"]:
        return False, "candidate produced errors"
    if winrate(summary) < args.min_winrate:
        return False, f"winrate below {args.min_winrate:.2f}"

    for opponent, opponent_summary in summary["by_opponent"].items():
        opponent_min = args.min_opponent_winrate
        if opponent.startswith("champion:"):
            opponent_min = max(opponent_min, args.min_champion_winrate)
        if opponent == "production_hunter":
            opponent_min = max(opponent_min, args.min_production_hunter_winrate)
        if winrate(opponent_summary) < opponent_min:
            return False, f"{opponent} winrate below {opponent_min:.2f}"

    return True, "passed"


def candidate_snapshot(candidate):
    return {
        "name": candidate["name"],
        "base": candidate.get("base"),
        "path": candidate["path"],
        "params": candidate.get("params", {}),
    }


def new_playoff_score(candidate):
    return {
        "candidate": candidate["name"],
        "base": candidate.get("base"),
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "errors": 0,
        "production_delta": 0,
        "ship_delta": 0,
    }


def update_playoff_score(score, result, won, lost, draw, error, production_delta, ship_delta):
    score["games"] += 1
    score["production_delta"] += production_delta
    score["ship_delta"] += ship_delta

    if won:
        score["wins"] += 1
    elif lost:
        score["losses"] += 1
    elif draw:
        score["draws"] += 1
    elif error:
        score["errors"] += 1
        score["losses"] += 1


def add_playoff_result(score_a, score_b, record, name_a, name_b):
    final = record.get("final", {})
    a_final = final.get("0", {})
    b_final = final.get("1", {})
    production_delta = a_final.get("production", 0) - b_final.get("production", 0)
    ship_delta = a_final.get("total_ships", 0) - b_final.get("total_ships", 0)
    result = record["result"]

    a_won = result == "A_WIN"
    b_won = result == "B_WIN"
    draw = result == "DRAW"
    a_error = result == "A_ERROR"
    b_error = result == "B_ERROR"

    update_playoff_score(
        score_a,
        result,
        a_won or b_error,
        b_won or a_error,
        draw,
        a_error,
        production_delta,
        ship_delta,
    )
    update_playoff_score(
        score_b,
        result,
        b_won or a_error,
        a_won or b_error,
        draw,
        b_error,
        -production_delta,
        -ship_delta,
    )


def compact_playoff_score(score):
    games = score["games"]
    resolved = games - score["errors"]
    winrate_value = score["wins"] / resolved if resolved else 0.0
    avg_production_delta = score["production_delta"] / games if games else 0.0
    avg_ship_delta = score["ship_delta"] / games if games else 0.0
    score_value = (
        winrate_value
        + max(-0.08, min(0.08, avg_production_delta / 140.0))
        + max(-0.06, min(0.06, avg_ship_delta / 900.0))
        - (0.25 if score["errors"] else 0.0)
    )

    return {
        "candidate": score["candidate"],
        "base": score["base"],
        "games": games,
        "wins": score["wins"],
        "losses": score["losses"],
        "draws": score["draws"],
        "errors": score["errors"],
        "winrate": round(winrate_value, 4),
        "score": round(score_value, 4),
        "avg_production_delta": round(avg_production_delta, 2),
        "avg_ship_delta": round(avg_ship_delta, 2),
    }


def playoff_sort_key(score):
    compact = compact_playoff_score(score)
    return (
        compact["wins"],
        compact["score"],
        compact["avg_production_delta"],
        compact["avg_ship_delta"],
    )


def run_playoff_match(candidate_a, candidate_b, seeds, telemetry_file, match_info):
    score_a = new_playoff_score(candidate_a)
    score_b = new_playoff_score(candidate_b)
    jobs = []

    for seed in seeds:
        jobs.append(
            {
                "agent_a": candidate_a["path"],
                "agent_b": candidate_b["path"],
                "seed": seed,
                "name_a": candidate_a["name"],
                "name_b": candidate_b["name"],
                "metadata": {
                    "playoff": match_info,
                    "playoff_side": {
                        "a": candidate_a["name"],
                        "b": candidate_b["name"],
                    },
                    "playoff_order": "forward",
                },
            }
        )

        jobs.append(
            {
                "agent_a": candidate_b["path"],
                "agent_b": candidate_a["path"],
                "seed": seed,
                "name_a": candidate_b["name"],
                "name_b": candidate_a["name"],
                "metadata": {
                    "playoff": match_info,
                    "playoff_side": {
                        "a": candidate_b["name"],
                        "b": candidate_a["name"],
                    },
                    "playoff_order": "reverse",
                },
            }
        )

    for record in iter_job_results(jobs, match_info["workers"]):
        if record["playoff_order"] == "forward":
            add_playoff_result(
                score_a,
                score_b,
                record,
                candidate_a["name"],
                candidate_b["name"],
            )
        else:
            add_playoff_result(
                score_b,
                score_a,
                record,
                candidate_b["name"],
                candidate_a["name"],
            )
        telemetry_file.write(json.dumps(record, sort_keys=True) + "\n")

    if playoff_sort_key(score_a) >= playoff_sort_key(score_b):
        winner = candidate_a
        loser = candidate_b
    else:
        winner = candidate_b
        loser = candidate_a

    return {
        "winner": winner,
        "loser": loser,
        "report": {
            "match": match_info,
            "a": compact_playoff_score(score_a),
            "b": compact_playoff_score(score_b),
            "winner": winner["name"],
            "loser": loser["name"],
        },
    }


def run_playoff(candidates, round_index, args, telemetry_path):
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    bracket = list(candidates)
    rounds = []

    with telemetry_path.open("w", encoding="utf-8") as telemetry_file:
        playoff_round = 1
        while len(bracket) > 1:
            next_bracket = []
            round_report = {
                "round": playoff_round,
                "entrants": [candidate_snapshot(candidate) for candidate in bracket],
                "matches": [],
            }

            left = 0
            right = len(bracket) - 1
            if len(bracket) % 2 == 1:
                bye = bracket[0]
                next_bracket.append(bye)
                round_report["bye"] = candidate_snapshot(bye)
                left = 1

            match_index = 1
            while left < right:
                candidate_a = bracket[left]
                candidate_b = bracket[right]
                seed_start = (
                    args.seed_start
                    + round_index * 10000
                    + 2000
                    + playoff_round * 1000
                    + match_index * 100
                )
                seeds = range(seed_start, seed_start + args.playoff_seeds)
                match_info = {
                    "round": playoff_round,
                    "match": match_index,
                    "seed_start": seed_start,
                    "seeds": args.playoff_seeds,
                    "workers": args.workers,
                }
                result = run_playoff_match(
                    candidate_a,
                    candidate_b,
                    seeds,
                    telemetry_file,
                    match_info,
                )
                next_bracket.append(result["winner"])
                round_report["matches"].append(result["report"])
                print(
                    "playoff "
                    f"r{playoff_round}m{match_index}: "
                    f"{candidate_a['name']} vs {candidate_b['name']} -> "
                    f"{result['winner']['name']}",
                    flush=True,
                )
                left += 1
                right -= 1
                match_index += 1

            rounds.append(round_report)
            bracket = next_bracket
            playoff_round += 1

    return {
        "enabled": True,
        "telemetry": str(telemetry_path),
        "rounds": rounds,
        "champion": bracket[0],
    }


def next_version_name(state, candidate_name):
    index = int(state.get("promotions", 0)) + 1
    return f"auto_v{index:03d}_{utc_stamp()}_{candidate_name}"


def package_submission(source_path, package_dir, tar_path):
    package_dir.mkdir(parents=True, exist_ok=True)
    package_main = package_dir / "main.py"
    shutil.copyfile(source_path, package_main)
    shutil.copyfile(source_path, REPO_ROOT / "submission.py")

    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(package_main, arcname="main.py")

    return package_main


def append_version_readme(version_name, source_path, summary, reason):
    readme = REPO_ROOT / "agents" / "versions" / "README.md"
    readme.parent.mkdir(parents=True, exist_ok=True)
    text = ""
    if readme.exists():
        text = readme.read_text(encoding="utf-8").rstrip() + "\n\n"

    lines = [
        f"## {version_name}",
        "",
        "Auto-promoted local candidate.",
        "",
        f"- Source: `{source_path}`",
        f"- Decision: {reason}",
        f"- Validation winrate: `{winrate(summary):.3f}`",
        f"- Validation score: `{score_summary(summary):.3f}`",
        f"- Avg production delta: `{avg(summary, 'production_delta'):.1f}`",
        f"- Avg ship delta: `{avg(summary, 'ship_delta'):.1f}`",
        "- Opponent breakdown:",
    ]
    for opponent, opponent_summary in summary["by_opponent"].items():
        lines.append(
            f"  - `{opponent}`: {winrate(opponent_summary):.3f} "
            f"({opponent_summary['wins']}/{opponent_summary['games']})"
        )

    readme.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")


def promote_candidate(candidate, summary, state, args, reason):
    version_name = next_version_name(state, candidate["name"])
    versions_dir = REPO_ROOT / "agents" / "versions"
    version_path = versions_dir / f"{version_name}.py"
    versions_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(candidate["path"], version_path)

    package_main = package_submission(
        version_path,
        REPO_ROOT / "submission_package",
        REPO_ROOT / "submission.tar.gz",
    )
    append_version_readme(version_name, version_path, summary, reason)

    state["promotions"] = int(state.get("promotions", 0)) + 1
    state["best_version"] = version_name
    state["best_version_path"] = str(version_path)
    state["last_promotion_at"] = datetime.now(timezone.utc).isoformat()
    state["last_package_main"] = str(package_main)

    return version_name, version_path


def default_kaggle_bin():
    local_bin = REPO_ROOT / ".venv" / "bin" / "kaggle"
    if local_bin.exists():
        return str(local_bin)
    return os.environ.get("KAGGLE_BIN", "kaggle")


def can_submit(state, args):
    if not args.submit:
        return False, "submit disabled"
    if int(state.get("submissions", 0)) >= args.max_submissions:
        return False, "max submissions reached"

    last = state.get("last_submit_epoch")
    if last:
        elapsed = time.time() - float(last)
        cooldown = args.submit_cooldown_minutes * 60
        if elapsed < cooldown:
            minutes = math.ceil((cooldown - elapsed) / 60)
            return False, f"submit cooldown active ({minutes}m remaining)"

    return True, "ready"


def submit_package(version_name, version_path, summary, state, args):
    ok, reason = can_submit(state, args)
    if not ok:
        return {"status": "skipped", "reason": reason}

    message = (
        f"{version_name}: auto local wr={winrate(summary):.3f} "
        f"score={score_summary(summary):.3f}"
    )
    command = [
        args.kaggle_bin,
        "competitions",
        "submit",
        args.competition,
        "-f",
        str(REPO_ROOT / "submission.tar.gz"),
        "-m",
        message[:120],
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        state["submissions"] = int(state.get("submissions", 0)) + 1
        state["last_submit_epoch"] = time.time()
        state["last_submit_at"] = datetime.now(timezone.utc).isoformat()
        state["last_submit_message"] = message[:120]
        state["last_submitted_version"] = version_name
        state["last_submitted_version_path"] = str(version_path)

    return {
        "status": "submitted" if result.returncode == 0 else "error",
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "message": message[:120],
    }


def run_round(args, state, rng):
    round_index = int(state.get("round", 0)) + 1
    stamp = utc_stamp()
    run_dir = REPO_ROOT / args.output_dir / f"round_{round_index:04d}_{stamp}"
    candidate_dir = run_dir / "candidates"
    telemetry_dir = REPO_ROOT / args.telemetry_dir

    print(f"round {round_index}: generating {args.candidates_per_round} candidates")
    replay_base_items, replay_signals = load_replay_base(args.replay_signals)
    
    elite_pool_path = REPO_ROOT / "training" / "elite_pool.json"
    elites = []
    if elite_pool_path.exists():
        elite_data = json.loads(elite_pool_path.read_text(encoding="utf-8"))
        for item in elite_data:
            elites.append((f"elite_{item['name']}", item["params"]))
            
    # Load Best Submitted Champion as heavily weighted template
    champion_base = []
    if state.get("best_version_path"):
        best_path = Path(state["best_version_path"])
        if best_path.exists():
            import re
            content = best_path.read_text(encoding="utf-8")
            match = re.search(r'BASE_PARAMS\s*=\s*(\{.*?\})', content, re.DOTALL)
            if match:
                try:
                    best_params = eval(match.group(1))
                    # Add it 10 times to give it a very high probability of being mutated
                    champion_base.extend([("champion_template", best_params)] * 10)
                except Exception:
                    pass

    base_items = list(CANDIDATES.items()) + replay_base_items + elites + champion_base
    candidates = generate_round_candidates(
        round_index,
        args.candidates_per_round,
        candidate_dir,
        rng,
        base_items,
    )
    candidates.extend(load_candidate_agents(args.candidate_agent, round_index))
    save_json(run_dir / "candidates.json", candidates)

    smoke_seeds = range(
        args.seed_start + round_index * 10000,
        args.seed_start + round_index * 10000 + args.smoke_seeds,
    )
    smoke_path = telemetry_dir / f"round_{round_index:04d}_smoke.jsonl"
    smoke_summaries = evaluate_candidates(
        candidates,
        args.opponents,
        smoke_seeds,
        smoke_path,
        args,
    )
    ranked = rank_candidates(candidates, smoke_summaries)
    finalists = ranked[: args.finalists]

    validation_seeds = range(
        args.seed_start + round_index * 10000 + 1000,
        args.seed_start + round_index * 10000 + 1000 + args.validation_seeds,
    )
    validation_path = telemetry_dir / f"round_{round_index:04d}_validation.jsonl"
    validation_summaries = evaluate_candidates(
        finalists,
        args.opponents,
        validation_seeds,
        validation_path,
        args,
    )
    final_ranked = rank_candidates(finalists, validation_summaries)
    best = final_ranked[0]
    best_summary = validation_summaries[best["name"]]
    gate_results = []
    selected = None
    selected_summary = None
    selected_reason = None
    qualified = []

    for candidate in final_ranked:
        summary = validation_summaries[candidate["name"]]
        candidate_passed, candidate_reason = passes_gate(summary, args)
        gate_results.append(
            {
                "candidate": candidate["name"],
                "passed": candidate_passed,
                "reason": candidate_reason,
                "summary": compact_summary(summary),
            }
        )
        if candidate_passed:
            qualified.append(candidate)

    passed = bool(qualified)
    playoff_report = {
        "enabled": bool(args.playoff),
        "qualified": [candidate_snapshot(candidate) for candidate in qualified],
        "qualified_count": len(qualified),
        "played": False,
    }

    if passed and args.playoff and len(qualified) > 1:
        playoff_path = telemetry_dir / f"round_{round_index:04d}_playoff.jsonl"
        playoff_result = run_playoff(qualified, round_index, args, playoff_path)
        selected = playoff_result["champion"]
        selected_summary = validation_summaries[selected["name"]]
        selected_reason = f"passed gate and won playoff from {len(qualified)} entrants"
        playoff_report.update(
            {
                "played": True,
                "telemetry": playoff_result["telemetry"],
                "rounds": playoff_result["rounds"],
                "champion": candidate_snapshot(selected),
            }
        )
    elif passed:
        selected = qualified[0]
        selected_summary = validation_summaries[selected["name"]]
        selected_reason = "passed gate; no playoff needed"
        playoff_report["champion"] = candidate_snapshot(selected)

    reason = selected_reason if passed else f"no finalist passed; best failed: {gate_results[0]['reason']}"

    round_report = {
        "round": round_index,
        "generated_at": stamp,
        "opponents": args.opponents,
        "workers": args.workers,
        "smoke_telemetry": str(smoke_path),
        "validation_telemetry": str(validation_path),
        "replay_signal": {
            "path": str(REPO_ROOT / args.replay_signals),
            "examples": replay_signals.get("examples", 0),
            "base_count": len(replay_base_items),
            "base_names": [name for name, _ in replay_base_items],
            "target_owner_rates": replay_signals.get("target_owner_rates", {}),
            "phase_rates": replay_signals.get("phase_rates", {}),
        },
        "candidate_bases": candidate_rollup(candidates),
        "finalist_bases": candidate_rollup(finalists),
        "best": best,
        "best_summary": compact_summary(best_summary),
        "validated_finalists": gate_results,
        "playoff": playoff_report,
        "gate": {"passed": passed, "reason": reason},
    }
    save_json(run_dir / "round_report.json", round_report)
    
    # ELITE POOL UPDATES
    elite_pool_path.parent.mkdir(parents=True, exist_ok=True)
    elite_data = []
    if elite_pool_path.exists():
        elite_data = json.loads(elite_pool_path.read_text(encoding="utf-8"))
        
    for candidate in final_ranked:
        summary = validation_summaries[candidate["name"]]
        if winrate(summary) >= 0.50:
            if not any(e["name"] == candidate["name"] for e in elite_data):
                elite_data.append({
                    "name": candidate["name"],
                    "params": candidate.get("params", {}),
                    "winrate": winrate(summary),
                    "score": score_summary(summary)
                })
                
    # Sort elites by score and keep top 50
    elite_data.sort(key=lambda x: x.get("score", 0), reverse=True)
    elite_data = elite_data[:50]
    elite_pool_path.write_text(json.dumps(elite_data, indent=2), encoding="utf-8")

    state["round"] = round_index
    state["last_round_at"] = datetime.now(timezone.utc).isoformat()
    state["last_round_report"] = str(run_dir / "round_report.json")

    if not passed:
        print(f"round {round_index}: no promotion ({reason})")
        return round_report

    version_name, version_path = promote_candidate(
        selected,
        selected_summary,
        state,
        args,
        reason,
    )
    submit_result = submit_package(version_name, version_path, selected_summary, state, args)
    round_report["promotion"] = {
        "candidate": selected["name"],
        "version_name": version_name,
        "version_path": str(version_path),
        "submit": submit_result,
    }
    save_json(run_dir / "round_report.json", round_report)
    print(f"round {round_index}: promoted {version_name}; submit={submit_result['status']}")
    return round_report


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--candidates-per-round", type=int, default=12)
    parser.add_argument(
        "--candidate-agent",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Add a hand-written agent file to each round's candidate pool.",
    )
    parser.add_argument("--finalists", type=int, default=3)
    parser.add_argument("--smoke-seeds", type=int, default=4)
    parser.add_argument("--validation-seeds", type=int, default=12)
    parser.add_argument(
        "--playoff",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run a seeded head-to-head playoff among all gate-passing finalists.",
    )
    parser.add_argument("--playoff-seeds", type=int, default=6)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel local match workers. Use 4-6 on an M2 MacBook Air.",
    )
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--opponents", nargs="+", default=DEFAULT_OPPONENTS)
    parser.add_argument(
        "--replay-signals",
        type=Path,
        default=Path("training/replay_signals.json"),
    )
    parser.add_argument("--min-winrate", type=float, default=0.62)
    parser.add_argument("--min-opponent-winrate", type=float, default=0.54)
    parser.add_argument("--min-champion-winrate", type=float, default=0.56)
    parser.add_argument("--min-production-hunter-winrate", type=float, default=0.58)
    parser.add_argument("--min-validation-games", type=int, default=60)
    parser.add_argument("--sleep-seconds", type=int, default=60)
    parser.add_argument("--random-seed", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("auto_runs"))
    parser.add_argument("--telemetry-dir", type=Path, default=Path("telemetry/auto"))
    parser.add_argument("--state", type=Path, default=Path("auto_runs/state.json"))
    parser.add_argument("--competition", default=DEFAULT_COMPETITION)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--max-submissions", type=int, default=1)
    parser.add_argument("--submit-cooldown-minutes", type=int, default=120)
    parser.add_argument("--kaggle-bin", default=default_kaggle_bin())
    return parser.parse_args()


def main():
    args = parse_args()
    args.workers = max(1, args.workers)
    rng = random.Random(args.random_seed)
    state_path = REPO_ROOT / args.state
    state = load_state(state_path)

    completed = 0
    while args.continuous or completed < args.rounds:
        try:
            report = run_round(args, state, rng)
            save_json(state_path, state)
            completed += 1
            if not args.continuous and completed >= args.rounds:
                break
            if report.get("promotion") and not args.continuous:
                break
            time.sleep(args.sleep_seconds)
        except KeyboardInterrupt:
            save_json(state_path, state)
            raise

    save_json(state_path, state)


if __name__ == "__main__":
    main()
