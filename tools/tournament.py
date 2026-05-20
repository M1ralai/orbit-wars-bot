import argparse
import json
from itertools import combinations
from pathlib import Path

from kaggle_environments import make

AGENTS = {
    "main": "main.py",
    "main_v2": "agents/main_v2.py",
    "v0_1": "agents/versions/v0_1.py",
    "v0_2": "agents/versions/v0_2.py",
    "random": "random",
    "greedy_nearest": "agents/greedy_nearest.py",
    "aggressive": "agents/aggressive_rusher.py",
    "production_hunter": "agents/production_hunter.py",
}

def owner_stats(observation):
    planets = observation.get("planets", [])
    fleets = observation.get("fleets", [])

    stats = {
        "-1": {
            "planet_count": 0,
            "production": 0,
            "planet_ships": 0,
            "fleet_count": 0,
            "fleet_ships": 0,
            "total_ships": 0,
        },
        "0": {
            "planet_count": 0,
            "production": 0,
            "planet_ships": 0,
            "fleet_count": 0,
            "fleet_ships": 0,
            "total_ships": 0,
        },
        "1": {
            "planet_count": 0,
            "production": 0,
            "planet_ships": 0,
            "fleet_count": 0,
            "fleet_ships": 0,
            "total_ships": 0,
        },
    }

    for planet in planets:
        owner = str(planet[1])
        ships = int(planet[5])

        stats[owner]["planet_count"] += 1
        stats[owner]["production"] += int(planet[6])
        stats[owner]["planet_ships"] += ships
        stats[owner]["total_ships"] += ships

    for fleet in fleets:
        owner = str(fleet[1])
        ships = int(fleet[5])

        stats[owner]["fleet_count"] += 1
        stats[owner]["fleet_ships"] += ships
        stats[owner]["total_ships"] += ships

    return stats


def timeline_summary(steps):
    checkpoints = []

    for index, step in enumerate(steps):
        observation = getattr(step[0], "observation", {}) or {}
        if index not in (0, len(steps) - 1) and index % 50 != 0:
            continue

        stats = owner_stats(observation)
        checkpoints.append(
            {
                "step": index,
                "planet_count": {
                    "neutral": stats["-1"]["planet_count"],
                    "a": stats["0"]["planet_count"],
                    "b": stats["1"]["planet_count"],
                },
                "production": {
                    "neutral": stats["-1"]["production"],
                    "a": stats["0"]["production"],
                    "b": stats["1"]["production"],
                },
                "total_ships": {
                    "neutral": stats["-1"]["total_ships"],
                    "a": stats["0"]["total_ships"],
                    "b": stats["1"]["total_ships"],
                },
            }
        )

    return checkpoints


def result_from_final(final):
    a = final[0]
    b = final[1]

    if a.status != "DONE":
        return "A_ERROR"
    if b.status != "DONE":
        return "B_ERROR"

    if a.reward > b.reward:
        return "A_WIN"
    if b.reward > a.reward:
        return "B_WIN"
    return "DRAW"


def run_match(agent_a, agent_b, seed, names=None, include_timeline=False):
    env = make("orbit_wars", configuration={"seed": seed}, debug=False)
    env.run([agent_a, agent_b])

    final = env.steps[-1]
    a = final[0]
    b = final[1]
    result = result_from_final(final)
    observation = getattr(a, "observation", {}) or {}

    record = {
        "seed": seed,
        "agents": {
            "a": names[0] if names else agent_a,
            "b": names[1] if names else agent_b,
        },
        "result": result,
        "winner": "a" if result == "A_WIN" else "b" if result == "B_WIN" else None,
        "turns": len(env.steps),
        "rewards": {
            "a": a.reward,
            "b": b.reward,
        },
        "statuses": {
            "a": a.status,
            "b": b.status,
        },
        "final": owner_stats(observation),
    }

    if include_timeline:
        record["timeline"] = timeline_summary(env.steps)

    return record


def new_score():
    return {
        "a_wins": 0,
        "b_wins": 0,
        "draws": 0,
        "a_errors": 0,
        "b_errors": 0,
        "games": 0,
        "a_winrate": 0.0,
    }


def update_score(score, result):
    score["games"] += 1

    if result == "A_WIN":
        score["a_wins"] += 1
    elif result == "B_WIN":
        score["b_wins"] += 1
    elif result == "DRAW":
        score["draws"] += 1
    elif result == "A_ERROR":
        score["a_errors"] += 1
    elif result == "B_ERROR":
        score["b_errors"] += 1

    resolved_games = score["games"] - score["a_errors"] - score["b_errors"]
    score["a_winrate"] = score["a_wins"] / resolved_games if resolved_games else 0.0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--agents", nargs="+")
    parser.add_argument(
        "--agent-file",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Register an extra agent file for this run.",
    )
    parser.add_argument(
        "--matchup",
        action="append",
        metavar="A:B",
        help="Run only this named matchup. Can be passed more than once.",
    )
    parser.add_argument("--telemetry", type=Path)
    parser.add_argument("--timeline", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def build_agents(args):
    agents = dict(AGENTS)

    for spec in args.agent_file:
        try:
            name, path = spec.split("=", 1)
        except ValueError as exc:
            raise SystemExit(f"invalid agent file {spec!r}; expected NAME=PATH") from exc

        name = name.strip()
        path = path.strip()

        if not name or not path:
            raise SystemExit(f"invalid agent file {spec!r}; expected NAME=PATH")

        agents[name] = path

    selected = args.agents or list(agents)
    unknown = [name for name in selected if name not in agents]
    if unknown:
        raise SystemExit(f"unknown agent(s): {', '.join(unknown)}")

    return agents, selected


def iter_matchups(args, agents, selected_agents):
    if args.matchup:
        for matchup in args.matchup:
            try:
                name_a, name_b = matchup.split(":", 1)
            except ValueError as exc:
                raise SystemExit(f"invalid matchup {matchup!r}; expected A:B") from exc

            if name_a not in agents or name_b not in agents:
                raise SystemExit(f"unknown matchup agent in {matchup!r}")

            yield name_a, name_b
        return

    yield from combinations(selected_agents, 2)


def print_table(results):
    print("matchup,a_wins,b_wins,draws,a_errors,b_errors,games,a_winrate")
    for matchup, score in results.items():
        name_a, name_b = matchup.split(" vs ")
        print(
            ",".join(
                [
                    f"{name_a} vs {name_b}",
                    str(score["a_wins"]),
                    str(score["b_wins"]),
                    str(score["draws"]),
                    str(score["a_errors"]),
                    str(score["b_errors"]),
                    str(score["games"]),
                    f"{score['a_winrate']:.3f}",
                ]
            )
        )


def main():
    args = parse_args()
    agents, selected_agents = build_agents(args)
    results = {}
    seeds = range(args.seed_start, args.seed_start + args.seeds)

    telemetry_file = None
    if args.telemetry:
        args.telemetry.parent.mkdir(parents=True, exist_ok=True)
        telemetry_file = args.telemetry.open("w", encoding="utf-8")

    try:
        for name_a, name_b in iter_matchups(args, agents, selected_agents):
            a_path = agents[name_a]
            b_path = agents[name_b]
            matchup = f"{name_a} vs {name_b}"
            score = new_score()

            for seed in seeds:
                record = run_match(
                    a_path,
                    b_path,
                    seed,
                    names=(name_a, name_b),
                    include_timeline=args.timeline,
                )

                update_score(score, record["result"])

                if telemetry_file:
                    telemetry_file.write(json.dumps(record, sort_keys=True) + "\n")

            results[matchup] = score
    finally:
        if telemetry_file:
            telemetry_file.close()

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print_table(results)


if __name__ == "__main__":
    main()
