import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_records(path):
    with path.open(encoding="utf-8") as telemetry_file:
        for line in telemetry_file:
            line = line.strip()
            if line:
                yield json.loads(line)


def new_summary():
    return {
        "games": 0,
        "a_wins": 0,
        "b_wins": 0,
        "draws": 0,
        "errors": 0,
        "turns": 0,
        "production_delta": 0,
        "ship_delta": 0,
        "a_loss_seeds": [],
        "error_seeds": [],
    }


def update_summary(summary, record):
    result = record["result"]
    final = record.get("final", {})
    a_final = final.get("0", {})
    b_final = final.get("1", {})

    summary["games"] += 1
    summary["turns"] += record.get("turns", 0)
    summary["production_delta"] += a_final.get("production", 0) - b_final.get(
        "production", 0
    )
    summary["ship_delta"] += a_final.get("total_ships", 0) - b_final.get(
        "total_ships", 0
    )

    if result == "A_WIN":
        summary["a_wins"] += 1
    elif result == "B_WIN":
        summary["b_wins"] += 1
        summary["a_loss_seeds"].append(record["seed"])
    elif result == "DRAW":
        summary["draws"] += 1
    else:
        summary["errors"] += 1
        summary["error_seeds"].append(record["seed"])


def matchup_name(record):
    agents = record["agents"]
    return f"{agents['a']} vs {agents['b']}"


def print_summary(summaries):
    print(
        "matchup,games,a_winrate,draws,errors,avg_turns,"
        "avg_final_production_delta,avg_final_ship_delta,a_loss_seeds,error_seeds"
    )

    for matchup, summary in summaries.items():
        games = summary["games"]
        resolved_games = games - summary["errors"]
        a_winrate = summary["a_wins"] / resolved_games if resolved_games else 0.0
        avg_turns = summary["turns"] / games if games else 0.0
        avg_production_delta = summary["production_delta"] / games if games else 0.0
        avg_ship_delta = summary["ship_delta"] / games if games else 0.0
        a_loss_seeds = ";".join(map(str, summary["a_loss_seeds"][:12]))
        error_seeds = ";".join(map(str, summary["error_seeds"][:12]))

        print(
            ",".join(
                [
                    matchup,
                    str(games),
                    f"{a_winrate:.3f}",
                    str(summary["draws"]),
                    str(summary["errors"]),
                    f"{avg_turns:.1f}",
                    f"{avg_production_delta:.1f}",
                    f"{avg_ship_delta:.1f}",
                    a_loss_seeds,
                    error_seeds,
                ]
            )
        )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("telemetry", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    summaries = defaultdict(new_summary)

    for record in load_records(args.telemetry):
        update_summary(summaries[matchup_name(record)], record)

    print_summary(summaries)


if __name__ == "__main__":
    main()
