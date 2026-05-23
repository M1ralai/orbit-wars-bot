import argparse
import ast
import json
import math
import multiprocessing
import os
import platform
import random
import shutil
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Use fork on macOS — workers inherit loaded kaggle_environments (1.27x faster)
if platform.system() == "Darwin":
    multiprocessing.set_start_method("fork", force=True)


SCRIPT_DIR = Path(__file__).resolve().parent
FAMILY_ROOT = SCRIPT_DIR.parents[0]
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = FAMILY_ROOT
for import_root in (str(SCRIPT_DIR), str(PROJECT_ROOT / "tools")):
    if import_root in sys.path:
        sys.path.remove(import_root)
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.append(str(PROJECT_ROOT / "tools"))

from generate_agents import CANDIDATES, TEMPLATE  # noqa: E402
from tournament import AGENTS, run_match  # noqa: E402


DEFAULT_OPPONENTS = ["champion"]
DEFAULT_COMPETITION = "orbit-wars"

INT_PARAMS = {
    "min_ships",
    "min_reserve",
    "neutral_bonus",
    "neutral_tax",
    "enemy_bonus",
    "counter_bonus",
    "pressure_max",
    "pressure_divisor",
    "production_weight",
    "high_production_weight",
    "high_prod_tax",
    "short_hop_range",
    "overkill",
    "high_prod_extra",
    "enemy_extra",
    "max_attacks_per_turn",
    "comet_bonus",
    "evac_minor_prod",
    "sync_min_target_prod",
    "sync_min_target_ships",
    "snipe_max_step",
    "snipe_overkill",
    "honeypot_min_prod",
    "honeypot_reserve",
    "feint_interval",
    "feint_min_margin",
}

PARAM_BOUNDS = {
    "min_ships": (3, 26),
    "min_reserve": (1, 22),
    "reserve_prod_mult": (1.0, 7.0),
    "panic_reserve_mult": (0.0, 2.2),
    "neutral_bonus": (0, 40),
    "neutral_tax": (0, 28),
    "enemy_bonus": (14, 86),
    "enemy_weak_bonus": (0.0, 5.0),
    "counter_bonus": (0, 50),
    "pressure_max": (0, 110),
    "pressure_divisor": (5, 90),
    "production_weight": (6, 64),
    "high_production_weight": (10, 78),
    "high_prod_tax": (0, 50),
    "distance_weight": (1.0, 5.0),
    "high_distance_weight": (0.8, 4.5),
    "short_hop_bonus": (0.0, 4.5),
    "short_hop_range": (12, 58),
    "ship_weight": (0.4, 3.0),
    "high_ship_weight": (0.3, 2.8),
    "overkill": (0, 10),
    "high_prod_extra": (0, 7),
    "enemy_extra": (0, 18),
    "attack_fraction": (0.18, 0.99),
    "max_attacks_per_turn": (1, 12),
    "comet_bonus": (-10, 24),
    "staging_penalty": (3.0, 42.0),
    "defense_worth_factor": (3.0, 25.0),
    "counter_attack_bonus": (3.0, 55.0),
    "production_forecast_mult": (0.0, 2.5),
    "evac_eta_threshold": (1.2, 7.0),
    "evac_minor_prod": (1, 4),
    "sync_max_eta": (3.0, 24.0),
    "sync_min_target_prod": (1, 6),
    "sync_min_target_ships": (12, 70),
    "snipe_max_step": (35, 220),
    "snipe_overkill": (1, 10),
    "honeypot_min_prod": (1, 6),
    "honeypot_reserve": (1, 12),
    "feint_interval": (3, 18),
    "feint_min_margin": (1, 6),
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


def normalize_family_path(path):
    path = Path(path)
    if path.is_absolute():
        return path
    if path.parts[:2] == ("families", "hybrid"):
        return PROJECT_ROOT / path
    return REPO_ROOT / path


def clamp(name, value):
    low, high = PARAM_BOUNDS[name]
    value = max(low, min(high, value))
    if name in INT_PARAMS:
        return int(round(value))
    return round(float(value), 4)


def param_prior(priors, name):
    if not priors:
        return None

    prior = priors.get("parameters", {}).get(name)
    if prior and prior.get("direction") in ("up", "down"):
        return prior
    return None


def mutate_params(base, rng, priors=None, adaptive_strength=0.0):
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

    # Decide if this candidate gets chaos mutation (20% chance)
    is_chaos = rng.random() < 0.10

    for name, value in list(params.items()):
        if rng.random() > 0.72:
            continue

        low, high = PARAM_BOUNDS[name]
        span = high - low
        prior = param_prior(priors, name)
        use_prior = prior and rng.random() < adaptive_strength
        direction = 1 if prior and prior.get("direction") == "up" else -1

        if name in INT_PARAMS:
            if use_prior:
                delta = rng.choice([1, 2, 3]) * direction
                if rng.random() < 0.2:
                    delta *= 2
            elif is_chaos:
                delta = rng.choice([-6, -5, -4, -3, 3, 4, 5, 6])
                if rng.random() < 0.3:
                    delta *= 2
            else:
                delta = rng.choice([-3, -2, -1, 1, 2, 3])
                if rng.random() < 0.2:
                    delta *= 2
            params[name] = clamp(name, value + delta)
        else:
            if use_prior:
                delta = rng.uniform(0.02, 0.12) * span * direction
            elif is_chaos:
                delta = rng.uniform(-0.25, 0.25) * span
            else:
                delta = rng.uniform(-0.12, 0.12) * span
            params[name] = clamp(name, value + delta)

    # Random full-reset: more params get fully randomized in chaos mode
    reset_count = rng.randint(3, 6) if is_chaos else rng.randint(1, 3)
    for name in rng.sample(list(params), k=min(reset_count, len(params))):
        low, high = PARAM_BOUNDS[name]
        prior = param_prior(priors, name)
        use_prior = prior and rng.random() < adaptive_strength
        if use_prior:
            low = max(low, prior["good_low"])
            high = min(high, prior["good_high"])

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
    params = dict(CANDIDATES["hybrid_cw014_dna"])
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


def generate_candidate_specs(round_index, count, rng, base_items, priors=None, adaptive_strength=0.0):
    records = []
    for candidate_index in range(count):
        base_name, base_params = rng.choice(base_items)
        params = mutate_params(base_params, rng, priors, adaptive_strength)
        name = f"auto_r{round_index:04d}_{candidate_index:03d}_{base_name}"
        records.append(
            {
                "name": name,
                "base": base_name,
                "params": params,
            }
        )
    return records


def materialize_candidate_specs(specs, output_dir):
    records = []
    for spec in specs:
        record = dict(spec)
        path = write_candidate(record["name"], record["params"], output_dir)
        record["path"] = str(path)
        records.append(record)
    return records


def load_base_params_from_agent(path):
    path = Path(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "BASE_PARAMS" for target in node.targets):
            continue
        try:
            params = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return None
        if isinstance(params, dict):
            return {
                name: clamp(name, params[name])
                for name in PARAM_BOUNDS
                if name in params
            }
    return None


def champion_base_item(state):
    champion_path = Path(champion_path_from_state(state))
    params = load_base_params_from_agent(champion_path)
    if not params:
        raise SystemExit(f"could not read BASE_PARAMS from hybrid champion: {champion_path}")
    # Truncate champion name to avoid filesystem path length limits
    stem = champion_path.stem
    if len(stem) > 60:
        stem = stem[:60]
    return f"hybrid_champ_{stem}", params, champion_path


def load_elite_items(path):
    path = normalize_family_path(path)
    if not path.exists():
        return []

    elite_data = json.loads(path.read_text(encoding="utf-8"))
    return [
        (f"elite_{item['name']}", item["params"])
        for item in elite_data
        if item.get("params")
    ]


def build_base_items(args, state, replay_base_items):
    champion_name, champion_params, champion_path = champion_base_item(state)
    if args.base_mode == "champion":
        return [(champion_name, champion_params)], {
            "mode": args.base_mode,
            "champion": champion_name,
            "champion_path": str(champion_path),
            "using_only_champion": True,
        }

    champion_weight = max(1, args.champion_base_weight)
    elites = load_elite_items(args.elite_pool_path)
    base_items = (
        list(CANDIDATES.items())
        + replay_base_items
        + elites
        + [(champion_name, champion_params)] * champion_weight
    )
    return base_items, {
        "mode": args.base_mode,
        "champion": champion_name,
        "champion_path": str(champion_path),
        "champion_weight": champion_weight,
        "seed_count": len(CANDIDATES),
        "replay_count": len(replay_base_items),
        "elite_count": len(elites),
    }


def generate_round_candidates(round_index, count, output_dir, rng, base_items, priors=None, adaptive_strength=0.0):
    specs = generate_candidate_specs(
        round_index,
        count,
        rng,
        base_items,
        priors,
        adaptive_strength,
    )
    return materialize_candidate_specs(specs, output_dir)


def select_ml_candidate_specs(specs, args, rng):
    report = {
        "enabled": bool(args.ml_ranker),
        "pool_size": len(specs),
        "selected_count": min(args.candidates_per_round, len(specs)),
        "used": False,
    }
    if not args.ml_ranker:
        return specs[: args.candidates_per_round], report

    try:
        from ml_ranker import load_ranker, rank_candidate_records, train_ranker
    except Exception as exc:
        report["reason"] = f"ml import failed: {exc}"
        return specs[: args.candidates_per_round], report

    model_path = normalize_family_path(args.ml_model_path)
    dataset_path = normalize_family_path(args.ml_dataset_path)
    priors_path = normalize_family_path(args.ml_priors_path)

    train_metadata = {}
    if args.ml_retrain:
        train_metadata = train_ranker(
            output_dir=args.output_dir,
            dataset_path=dataset_path,
            model_path=model_path,
            min_games=args.ml_min_games,
            min_samples=args.ml_min_samples,
            priors_path=priors_path,
        )
        report["train"] = train_metadata
        if not train_metadata.get("trained"):
            report["reason"] = train_metadata.get("reason", "no trained model")
            return specs[: args.candidates_per_round], report

    payload = load_ranker(model_path)
    if not payload:
        report["reason"] = train_metadata.get("reason", "no trained model")
        return specs[: args.candidates_per_round], report

    ranked = rank_candidate_records(
        specs,
        model_path=model_path,
        priors_path=priors_path,
    )
    if not ranked:
        report["reason"] = "model produced no scores"
        return specs[: args.candidates_per_round], report

    selected_count = min(args.candidates_per_round, len(ranked))
    exploration_count = min(
        selected_count - 1,
        max(0, int(round(selected_count * args.ml_exploration_rate))),
    )
    exploit_count = selected_count - exploration_count
    selected = list(ranked[:exploit_count])
    exploration_pool = list(ranked[exploit_count:])
    rng.shuffle(exploration_pool)
    selected.extend(exploration_pool[:exploration_count])

    rank_by_name = {record["name"]: index for index, record in enumerate(ranked, start=1)}
    for record in selected:
        record["ml_rank"] = rank_by_name[record["name"]]
        record["ml_selected"] = True

    top = [
        {
            "name": record["name"],
            "base": record.get("base"),
            "ml_score": record.get("ml_score"),
            "ml_rank": index,
        }
        for index, record in enumerate(ranked[:10], start=1)
    ]
    report.update(
        {
            "used": True,
            "selected_count": selected_count,
            "exploit_count": exploit_count,
            "exploration_count": exploration_count,
            "model_path": str(model_path if model_path.is_absolute() else REPO_ROOT / model_path),
            "metadata": payload.get("metadata", {}),
            "top": top,
            "selected": [
                {
                    "name": record["name"],
                    "base": record.get("base"),
                    "ml_score": record.get("ml_score"),
                    "ml_rank": record.get("ml_rank"),
                }
                for record in selected
            ],
        }
    )
    return selected, report


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
        state.get("best_version_path"),
        state.get("last_submitted_version_path"),
        state.get("submitted_version_path"),
    ]

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


def percentile(values, q):
    values = sorted(values)
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[int(position)]
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def load_adaptive_priors(args):
    if not args.adaptive_mutation:
        return {"enabled": False, "reason": "disabled"}

    output_dir = REPO_ROOT / args.output_dir
    reports = sorted(
        output_dir.glob("round_*/round_report.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[: args.adaptive_history_rounds]
    samples = {name: [] for name in PARAM_BOUNDS}
    report_count = 0
    candidate_count = 0

    for report_path in reports:
        candidates_path = report_path.parent / "candidates.json"
        if not candidates_path.exists():
            continue

        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        candidate_by_name = {candidate["name"]: candidate for candidate in candidates}
        validated = report.get("validated_finalists", [])
        if not validated:
            continue

        report_count += 1
        for result in validated:
            summary = result.get("summary", {})
            if summary.get("games", 0) < 10:
                continue

            candidate = candidate_by_name.get(result.get("candidate"))
            if not candidate:
                continue

            params = candidate.get("params", {})
            winrate_value = float(summary.get("winrate", 0.0))
            score_value = float(summary.get("score", winrate_value))
            quality = winrate_value * 0.75 + score_value * 0.25
            candidate_count += 1

            for name in PARAM_BOUNDS:
                if name in params:
                    samples[name].append(
                        {
                            "value": float(params[name]),
                            "quality": quality,
                            "winrate": winrate_value,
                        }
                    )

    priors = {}
    for name, param_samples in samples.items():
        if len(param_samples) < args.adaptive_min_samples:
            continue

        ordered = sorted(param_samples, key=lambda item: item["quality"])
        bucket_size = max(3, len(ordered) // 3)
        bad = ordered[:bucket_size]
        good = ordered[-bucket_size:]

        good_values = [item["value"] for item in good]
        bad_values = [item["value"] for item in bad]
        good_avg = sum(good_values) / len(good_values)
        bad_avg = sum(bad_values) / len(bad_values)
        low, high = PARAM_BOUNDS[name]
        span = high - low
        min_gap = max(span * 0.035, 0.25 if name in INT_PARAMS else 0.015)
        gap = good_avg - bad_avg

        if abs(gap) < min_gap:
            continue

        good_low = percentile(good_values, 0.15)
        good_high = percentile(good_values, 0.85)
        if good_high <= good_low:
            good_low = max(low, good_avg - span * 0.05)
            good_high = min(high, good_avg + span * 0.05)

        priors[name] = {
            "direction": "up" if gap > 0 else "down",
            "confidence": round(min(1.0, abs(gap) / span * 4.0), 4),
            "samples": len(param_samples),
            "good_avg": round(good_avg, 4),
            "bad_avg": round(bad_avg, 4),
            "good_low": clamp(name, good_low),
            "good_high": clamp(name, good_high),
            "avg_good_quality": round(sum(item["quality"] for item in good) / len(good), 4),
            "avg_bad_quality": round(sum(item["quality"] for item in bad) / len(bad), 4),
        }

    return {
        "enabled": True,
        "history_rounds": len(reports),
        "reports_used": report_count,
        "validated_candidates": candidate_count,
        "parameters": priors,
    }


def compact_adaptive_priors(priors):
    parameters = priors.get("parameters", {})
    up = sorted(
        [name for name, prior in parameters.items() if prior["direction"] == "up"],
        key=lambda name: parameters[name]["confidence"],
        reverse=True,
    )
    down = sorted(
        [name for name, prior in parameters.items() if prior["direction"] == "down"],
        key=lambda name: parameters[name]["confidence"],
        reverse=True,
    )
    return {
        "enabled": priors.get("enabled", False),
        "history_rounds": priors.get("history_rounds", 0),
        "reports_used": priors.get("reports_used", 0),
        "validated_candidates": priors.get("validated_candidates", 0),
        "strength": priors.get("strength", 0.0),
        "up": up[:8],
        "down": down[:8],
        "parameter_count": len(parameters),
    }


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


def resolve_opponents_once(opponents, state_path):
    """Resolve all opponent aliases to paths once, avoiding repeated disk reads."""
    resolved = []
    for opponent in opponents:
        opponent_path = resolve_agent(opponent, state_path)
        opponent_name = opponent_label(opponent, opponent_path)
        resolved.append((opponent, opponent_path, opponent_name))
    return resolved


def build_candidate_jobs(candidate, resolved_opponents, seeds):
    """Build all match jobs for a single candidate against resolved opponents."""
    candidate_path = candidate["path"]
    jobs = []
    for _, opponent_path, opponent_name in resolved_opponents:
        for seed in seeds:
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
                        "opponent_alias": _,
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
                        "opponent_alias": _,
                        "opponent_path": opponent_path,
                        "candidate_side": "b",
                    },
                }
            )
    return jobs


def evaluate_candidates(candidates, opponents, seeds, telemetry_path, args):
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve opponents once instead of per-seed per-candidate
    resolved_opponents = resolve_opponents_once(opponents, args.state)

    # Build ALL jobs for ALL candidates upfront
    all_jobs = []
    for candidate in candidates:
        all_jobs.extend(build_candidate_jobs(candidate, resolved_opponents, seeds))

    total_jobs = len(all_jobs)
    games_per_candidate = total_jobs // len(candidates) if candidates else 0
    print(f"  running {total_jobs} matches ({len(candidates)} candidates x {games_per_candidate} games) with {args.workers} workers...", flush=True)

    # Run everything in a single shared pool
    summaries = {c["name"]: new_summary(c["name"]) for c in candidates}
    completed = 0
    completed_candidates = set()
    with telemetry_path.open("w", encoding="utf-8") as telemetry_file:
        for record in iter_job_results(all_jobs, args.workers):
            summary = summaries[record["candidate"]]
            add_result(summary, record, record["candidate_side"], record["opponent"])
            telemetry_file.write(json.dumps(record, sort_keys=True) + "\n")
            completed += 1

            # Print candidate result as soon as all its games are done
            if summary["games"] >= games_per_candidate and record["candidate"] not in completed_candidates:
                completed_candidates.add(record["candidate"])
                print(
                    f"  [{len(completed_candidates)}/{len(candidates)}] {record['candidate']}: "
                    f"winrate={winrate(summary):.3f} score={score_summary(summary):.3f} "
                    f"games={summary['games']}",
                    flush=True,
                )

    # Print any remaining candidates that didn't trigger above (safety net)
    for candidate in candidates:
        if candidate["name"] not in completed_candidates:
            summary = summaries[candidate["name"]]
            print(
                f"  [{len(candidates)}/{len(candidates)}] {candidate['name']}: "
                f"winrate={winrate(summary):.3f} score={score_summary(summary):.3f} "
                f"games={summary['games']}",
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


def build_playoff_round_jobs(bracket, playoff_round, round_index, args):
    """Build all jobs for one playoff round and return matchups + jobs."""
    matchups = []
    all_jobs = []
    next_bracket = []

    left = 0
    right = len(bracket) - 1
    bye = None
    if len(bracket) % 2 == 1:
        bye = bracket[0]
        next_bracket.append(bye)
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

        match_key = f"r{playoff_round}m{match_index}"
        matchups.append((match_key, candidate_a, candidate_b, match_info))

        for seed in seeds:
            all_jobs.append(
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
                        "playoff_match_key": match_key,
                    },
                }
            )
            all_jobs.append(
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
                        "playoff_match_key": match_key,
                    },
                }
            )

        left += 1
        right -= 1
        match_index += 1

    return matchups, all_jobs, next_bracket, bye


def run_playoff(candidates, round_index, args, telemetry_path):
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    bracket = list(candidates)
    rounds = []

    with telemetry_path.open("w", encoding="utf-8") as telemetry_file:
        playoff_round = 1
        while len(bracket) > 1:
            round_report = {
                "round": playoff_round,
                "entrants": [candidate_snapshot(candidate) for candidate in bracket],
                "matches": [],
            }

            matchups, all_jobs, next_bracket, bye = build_playoff_round_jobs(
                bracket, playoff_round, round_index, args
            )
            if bye:
                round_report["bye"] = candidate_snapshot(bye)

            # Build score trackers per match
            scores = {}
            matchup_map = {}
            for match_key, candidate_a, candidate_b, match_info in matchups:
                scores[match_key] = (
                    new_playoff_score(candidate_a),
                    new_playoff_score(candidate_b),
                    candidate_a,
                    candidate_b,
                    match_info,
                )

            # Run ALL playoff round jobs in a single pool
            for record in iter_job_results(all_jobs, args.workers):
                match_key = record["playoff_match_key"]
                score_a, score_b, ca, cb, mi = scores[match_key]
                if record["playoff_order"] == "forward":
                    add_playoff_result(score_a, score_b, record, ca["name"], cb["name"])
                else:
                    add_playoff_result(score_b, score_a, record, cb["name"], ca["name"])
                telemetry_file.write(json.dumps(record, sort_keys=True) + "\n")

            # Determine winners
            for match_key, candidate_a, candidate_b, match_info in matchups:
                score_a, score_b, _, _, _ = scores[match_key]
                if playoff_sort_key(score_a) >= playoff_sort_key(score_b):
                    winner, loser = candidate_a, candidate_b
                else:
                    winner, loser = candidate_b, candidate_a
                next_bracket.append(winner)
                round_report["matches"].append({
                    "match": match_info,
                    "a": compact_playoff_score(score_a),
                    "b": compact_playoff_score(score_b),
                    "winner": winner["name"],
                    "loser": loser["name"],
                })
                print(
                    f"playoff {match_key}: "
                    f"{candidate_a['name']} vs {candidate_b['name']} -> "
                    f"{winner['name']}",
                    flush=True,
                )

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
    # Truncate candidate name to avoid filesystem path length explosion
    short_name = candidate_name[:80] if len(candidate_name) > 80 else candidate_name
    return f"auto_v{index:03d}_{utc_stamp()}_{short_name}"


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
    for root in (REPO_ROOT, PROJECT_ROOT):
        local_bin = root / ".venv" / "bin" / "kaggle"
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
    if args.base_mode == "mixed":
        replay_base_items, replay_signals = load_replay_base(args.replay_signals)
    else:
        replay_base_items, replay_signals = [], {}
    adaptive_priors = load_adaptive_priors(args)
    adaptive_strength = args.adaptive_strength if adaptive_priors.get("enabled") else 0.0
    adaptive_priors["strength"] = adaptive_strength
    if adaptive_priors.get("enabled"):
        save_json(normalize_family_path(args.ml_priors_path), adaptive_priors)
        prior_summary = compact_adaptive_priors(adaptive_priors)
        print(
            "adaptive mutation: "
            f"samples={prior_summary['validated_candidates']} "
            f"params={prior_summary['parameter_count']} "
            f"up={prior_summary['up'][:4]} "
            f"down={prior_summary['down'][:4]}",
            flush=True,
        )

    elite_pool_path = normalize_family_path(args.elite_pool_path)
    base_items, base_report = build_base_items(args, state, replay_base_items)
    print(
        "lineage base: "
        f"mode={base_report['mode']} "
        f"champion={base_report['champion']} "
        f"bases={len(base_items)}",
        flush=True,
    )
    pool_size = args.ml_pool_size if args.ml_ranker else args.candidates_per_round
    candidate_specs = generate_candidate_specs(
        round_index,
        pool_size,
        rng,
        base_items,
        adaptive_priors,
        adaptive_strength,
    )
    candidate_specs, ml_report = select_ml_candidate_specs(candidate_specs, args, rng)
    if ml_report.get("used"):
        metadata = ml_report.get("metadata", {})
        holdout = metadata.get("holdout", {})
        best_ml = ml_report.get("top", [{}])[0]
        print(
            "ml ranker: "
            f"pool={ml_report['pool_size']} selected={ml_report['selected_count']} "
            f"explore={ml_report['exploration_count']} "
            f"samples={metadata.get('samples', 0)} "
            f"best={best_ml.get('ml_score', 0):.3f} "
            f"mae={holdout.get('mae', 'na')}",
            flush=True,
        )
    elif args.ml_ranker:
        print(f"ml ranker skipped: {ml_report.get('reason', 'unknown reason')}", flush=True)

    candidates = materialize_candidate_specs(candidate_specs, candidate_dir)
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

    smoke_threshold = args.smoke_min_winrate
    valid_finalists = [c for c in ranked if winrate(smoke_summaries[c["name"]]) >= smoke_threshold]
    finalists = valid_finalists[: args.finalists]

    print(f"Smoke test complete. Filtered {len(valid_finalists)} finalists passing the winrate threshold of {smoke_threshold:.2f} (from {len(ranked)} total candidates).", flush=True)

    if not finalists:
        print(f"No candidates passed the smoke winrate gate of {smoke_threshold:.2f}. Skipping validation and playoffs for this round.", flush=True)
        validation_summaries = {}
        final_ranked = []
        gate_results = []
        for candidate in ranked:
            summary = smoke_summaries[candidate["name"]]
            gate_results.append(
                {
                    "candidate": candidate["name"],
                    "passed": False,
                    "reason": f"failed smoke test (winrate {winrate(summary):.3f} < {smoke_threshold:.2f})",
                    "summary": compact_summary(summary),
                }
            )
        qualified = []
        passed = False
        selected = None
        selected_summary = None
        selected_reason = "no candidates passed the smoke winrate threshold"
        best = ranked[0] if ranked else None
        best_summary = smoke_summaries[best["name"]] if best else {
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
        reason = "no candidates passed the smoke winrate threshold"
        validation_path = Path("")
        playoff_report = {
            "enabled": bool(args.playoff),
            "qualified": [],
            "qualified_count": 0,
            "played": False,
        }
    else:
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
        qualified = []
        selected = None
        selected_summary = None
        selected_reason = None

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

        # Record smoke-only candidates that did not qualify as finalists
        finalist_names = {c["name"] for c in finalists}
        for candidate in ranked:
            if candidate["name"] not in finalist_names:
                summary = smoke_summaries[candidate["name"]]
                gate_results.append(
                    {
                        "candidate": candidate["name"],
                        "passed": False,
                        "reason": f"failed smoke test (winrate {winrate(summary):.3f} < {smoke_threshold:.2f})",
                        "summary": compact_summary(summary),
                    }
                )

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
        "lineage_base": base_report,
        "finalist_bases": candidate_rollup(finalists),
        "adaptive_mutation": compact_adaptive_priors(adaptive_priors),
        "ml_ranker": ml_report,
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
    parser.add_argument("--smoke-min-winrate", type=float, default=0.30)
    parser.add_argument("--validation-seeds", type=int, default=30)
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
        "--base-mode",
        choices=("champion", "mixed"),
        default="champion",
        help="champion mutates only the current hybrid champion; mixed also uses seed/replay/elite bases.",
    )
    parser.add_argument(
        "--champion-base-weight",
        type=int,
        default=12,
        help="How heavily to weight the current hybrid champion when --base-mode mixed is used.",
    )
    parser.add_argument(
        "--adaptive-mutation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Bias mutations using recent validation winners and losers.",
    )
    parser.add_argument("--adaptive-history-rounds", type=int, default=24)
    parser.add_argument("--adaptive-min-samples", type=int, default=12)
    parser.add_argument("--adaptive-strength", type=float, default=0.65)
    parser.add_argument(
        "--ml-ranker",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Train/use the sklearn candidate ranker before local smoke tests.",
    )
    parser.add_argument("--ml-pool-size", type=int, default=512)
    parser.add_argument("--ml-exploration-rate", type=float, default=0.2)
    parser.add_argument("--ml-min-samples", type=int, default=40)
    parser.add_argument("--ml-min-games", type=int, default=10)
    parser.add_argument("--ml-model-path", type=Path, default=Path("training/ml_ranker.joblib"))
    parser.add_argument("--ml-dataset-path", type=Path, default=Path("training/ml_dataset.jsonl"))
    parser.add_argument("--ml-priors-path", type=Path, default=Path("training/adaptive_priors.json"))
    parser.add_argument("--elite-pool-path", type=Path, default=Path("training/elite_pool.json"))
    parser.add_argument(
        "--ml-retrain",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Retrain the sklearn ranker at the start of each round.",
    )
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
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    parser.add_argument("--telemetry-dir", type=Path, default=Path("telemetry"))
    parser.add_argument("--state", type=Path, default=Path("state.json"))
    parser.add_argument("--competition", default=DEFAULT_COMPETITION)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--max-submissions", type=int, default=1)
    parser.add_argument("--submit-cooldown-minutes", type=int, default=120)
    parser.add_argument("--kaggle-bin", default=default_kaggle_bin())
    return parser.parse_args()


def main():
    args = parse_args()
    args.workers = max(1, args.workers)
    args.adaptive_strength = max(0.0, min(1.0, args.adaptive_strength))
    args.ml_pool_size = max(args.candidates_per_round, args.ml_pool_size)
    args.ml_exploration_rate = max(0.0, min(0.6, args.ml_exploration_rate))
    args.smoke_min_winrate = max(0.0, min(1.0, args.smoke_min_winrate))
    args.champion_base_weight = max(1, args.champion_base_weight)
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
