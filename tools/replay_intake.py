import argparse
import json
import math
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CENTER_X = 50.0
CENTER_Y = 50.0
SUN_RADIUS = 10.0


def default_kaggle_bin():
    local_bin = REPO_ROOT / ".venv" / "bin" / "kaggle"
    if local_bin.exists():
        return str(local_bin)
    return os.environ.get("KAGGLE_BIN", "kaggle")


def parse_planet(planet):
    return {
        "id": planet[0],
        "owner": planet[1],
        "x": planet[2],
        "y": planet[3],
        "radius": planet[4],
        "ships": planet[5],
        "production": planet[6],
    }


def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def angle_diff(a, b):
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def segment_point_distance(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)


def path_hits_sun(src, target):
    return (
        segment_point_distance(
            CENTER_X,
            CENTER_Y,
            src["x"],
            src["y"],
            target["x"],
            target["y"],
        )
        <= SUN_RADIUS + 0.5
    )


def nearest_ray_target(src, angle, planets):
    best = None
    best_score = None

    for target in planets:
        if target["id"] == src["id"]:
            continue

        dx = target["x"] - src["x"]
        dy = target["y"] - src["y"]
        forward = dx * math.cos(angle) + dy * math.sin(angle)
        if forward <= 0:
            continue

        target_angle = math.atan2(dy, dx)
        diff = angle_diff(angle, target_angle)
        perpendicular = abs(dx * math.sin(angle) - dy * math.cos(angle))
        distance = math.hypot(dx, dy)
        score = diff * 100.0 + perpendicular * 0.8 + distance * 0.02

        if best_score is None or score < best_score:
            best = target
            best_score = score

    return best, best_score


def owner_bucket(owner, player):
    if owner == player:
        return "self"
    if owner == -1:
        return "neutral"
    return "enemy"


def summarize_observation(obs, player):
    planets = [parse_planet(planet) for planet in obs.get("planets", [])]
    fleets = obs.get("fleets", [])
    summary = {
        "planet_count": Counter(),
        "production": Counter(),
        "planet_ships": Counter(),
        "fleet_count": Counter(),
        "fleet_ships": Counter(),
    }

    for planet in planets:
        bucket = owner_bucket(planet["owner"], player)
        summary["planet_count"][bucket] += 1
        summary["production"][bucket] += planet["production"]
        summary["planet_ships"][bucket] += planet["ships"]

    for fleet in fleets:
        bucket = owner_bucket(fleet[1], player)
        summary["fleet_count"][bucket] += 1
        summary["fleet_ships"][bucket] += fleet[5]

    return {category: dict(values) for category, values in summary.items()}


def winners(rewards):
    if not rewards:
        return set()
    top = max(rewards)
    return {index for index, reward in enumerate(rewards) if reward == top}


def action_examples_from_replay(path, winners_only):
    data = json.loads(path.read_text(encoding="utf-8"))
    episode_id = data.get("info", {}).get("EpisodeId") or path.stem
    team_names = data.get("info", {}).get("TeamNames", [])
    winning_players = winners(data.get("rewards", []))

    for step_index, step in enumerate(data.get("steps", [])):
        for player_index, state in enumerate(step):
            if winners_only and player_index not in winning_players:
                continue

            action = state.get("action") or []
            if not action:
                continue

            obs = state.get("observation") or {}
            player = obs.get("player", player_index)
            planets = [parse_planet(planet) for planet in obs.get("planets", [])]
            planet_by_id = {planet["id"]: planet for planet in planets}
            obs_summary = summarize_observation(obs, player)

            for move in action:
                if not isinstance(move, list) or len(move) < 3:
                    continue

                source = planet_by_id.get(move[0])
                if not source:
                    continue

                target, target_score = nearest_ray_target(source, move[1], planets)
                target_bucket = owner_bucket(target["owner"], player) if target else "unknown"
                # Kaggle replays can pair an action with a post-launch observation.
                # Add the launched ships back to estimate the pre-launch garrison.
                source_ships = max(1, source["ships"] + move[2])

                yield {
                    "episode_id": episode_id,
                    "replay_path": str(path),
                    "step": obs.get("step", step_index),
                    "player_index": player_index,
                    "team_name": team_names[player_index] if player_index < len(team_names) else "",
                    "is_winner": player_index in winning_players,
                    "source": {
                        "id": source["id"],
                        "ships": source["ships"],
                        "production": source["production"],
                    },
                    "target": {
                        "id": target["id"] if target else None,
                        "owner_bucket": target_bucket,
                        "ships": target["ships"] if target else None,
                        "production": target["production"] if target else None,
                        "distance": round(dist(source, target), 3) if target else None,
                        "path_hits_sun": path_hits_sun(source, target) if target else None,
                        "ray_score": round(target_score, 3) if target_score is not None else None,
                    },
                    "action": {
                        "from_planet_id": move[0],
                        "angle": move[1],
                        "ships": move[2],
                        "source_ship_ratio": round(move[2] / source_ships, 4),
                    },
                    "observation_summary": obs_summary,
                }


def load_episode_ids(path):
    if not path.exists():
        return []

    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.append(line)
    return ids


def replay_path(replay_dir, episode_id):
    return replay_dir / f"episode-{episode_id}-replay.json"


def download_episode(kaggle_bin, episode_id, replay_dir):
    path = replay_path(replay_dir, episode_id)
    if path.exists():
        return {"episode_id": episode_id, "path": str(path), "status": "exists"}

    result = subprocess.run(
        [
            kaggle_bin,
            "competitions",
            "replay",
            str(episode_id),
            "-p",
            str(replay_dir),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    status = "downloaded" if result.returncode == 0 else "error"
    return {
        "episode_id": episode_id,
        "path": str(path),
        "status": status,
        "message": "" if status == "downloaded" else (result.stderr or result.stdout).strip(),
    }


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    index = int(round((len(values) - 1) * q))
    return values[index]


def phase_for_step(step):
    if step < 100:
        return "early"
    if step < 300:
        return "mid"
    return "late"


def rate_dict(counter, total):
    total = max(1, total)
    return {
        key: round(value / total, 4)
        for key, value in sorted(counter.items())
    }


def numeric_stats(values, digits=4):
    if not values:
        return {"avg": None, "p25": None, "p50": None, "p75": None}
    return {
        "avg": round(sum(values) / len(values), digits),
        "p25": percentile(values, 0.25),
        "p50": percentile(values, 0.50),
        "p75": percentile(values, 0.75),
    }


def empty_profile():
    return {
        "count": 0,
        "target_counts": Counter(),
        "production_counts": Counter(),
        "ratios": [],
        "distances": [],
        "high_prod_targets": 0,
    }


def add_to_profile(profile, example):
    target = example["target"]
    profile["count"] += 1
    profile["target_counts"][target["owner_bucket"]] += 1
    if target["production"] is not None:
        profile["production_counts"][str(target["production"])] += 1
        if target["production"] >= 3:
            profile["high_prod_targets"] += 1
    if target["distance"] is not None:
        profile["distances"].append(target["distance"])
    profile["ratios"].append(example["action"]["source_ship_ratio"])


def render_profile(profile):
    total = profile["count"]
    return {
        "examples": total,
        "target_owner_rates": rate_dict(profile["target_counts"], total),
        "target_production_counts": dict(sorted(profile["production_counts"].items())),
        "high_production_target_rate": round(
            profile["high_prod_targets"] / max(1, total),
            4,
        ),
        "source_ship_ratio": numeric_stats(profile["ratios"], digits=4),
        "target_distance": numeric_stats(profile["distances"], digits=3),
    }


def build_signals(examples):
    step_counts = Counter()
    overall = empty_profile()
    phase_profiles = {
        "early": empty_profile(),
        "mid": empty_profile(),
        "late": empty_profile(),
    }
    target_profiles = {
        "neutral": empty_profile(),
        "enemy": empty_profile(),
        "self": empty_profile(),
        "unknown": empty_profile(),
    }

    for example in examples:
        step = example["step"]
        phase = phase_for_step(step)
        target_bucket = example["target"]["owner_bucket"]
        step_counts[phase] += 1
        add_to_profile(overall, example)
        add_to_profile(phase_profiles[phase], example)
        add_to_profile(target_profiles.setdefault(target_bucket, empty_profile()), example)

    total = max(1, len(examples))
    rendered = render_profile(overall)
    rendered.update(
        {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "examples": len(examples),
            "phase_rates": rate_dict(step_counts, total),
            "phase_profiles": {
                phase: render_profile(profile)
                for phase, profile in phase_profiles.items()
            },
            "target_profiles": {
                target: render_profile(profile)
                for target, profile in target_profiles.items()
                if profile["count"]
            },
        }
    )
    return rendered


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-dir", type=Path, default=Path("replays"))
    parser.add_argument(
        "--episode-file",
        type=Path,
        default=Path("replays/external_episode_ids.txt"),
    )
    parser.add_argument("--download-missing", action="store_true")
    parser.add_argument("--kaggle-bin", default=default_kaggle_bin())
    parser.add_argument("--dataset", type=Path, default=Path("training/replay_examples.jsonl"))
    parser.add_argument("--signals", type=Path, default=Path("training/replay_signals.json"))
    parser.add_argument("--summary", type=Path, default=Path("training/replay_summary.json"))
    parser.add_argument("--winners-only", action="store_true", default=True)
    parser.add_argument("--include-all-players", dest="winners_only", action="store_false")
    return parser.parse_args()


def main():
    args = parse_args()
    replay_dir = REPO_ROOT / args.replay_dir
    replay_dir.mkdir(parents=True, exist_ok=True)

    downloads = []
    if args.download_missing:
        for episode_id in load_episode_ids(REPO_ROOT / args.episode_file):
            downloads.append(download_episode(args.kaggle_bin, episode_id, replay_dir))

    examples = []
    replay_paths = sorted(replay_dir.glob("episode-*-replay.json"))
    for path in replay_paths:
        examples.extend(action_examples_from_replay(path, args.winners_only))

    dataset_path = REPO_ROOT / args.dataset
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    with dataset_path.open("w", encoding="utf-8") as dataset_file:
        for example in examples:
            dataset_file.write(json.dumps(example, sort_keys=True) + "\n")

    signals = build_signals(examples)
    signals_path = REPO_ROOT / args.signals
    signals_path.parent.mkdir(parents=True, exist_ok=True)
    signals_path.write_text(json.dumps(signals, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "downloads": downloads,
        "replays": [str(path) for path in replay_paths],
        "dataset": str(dataset_path),
        "signals": str(signals_path),
        "examples": len(examples),
        "winners_only": args.winners_only,
    }
    summary_path = REPO_ROOT / args.summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(
        json.dumps(
            {
                "replays": len(replay_paths),
                "examples": len(examples),
                "dataset": str(dataset_path),
                "signals": str(signals_path),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
