import argparse
import json
from collections import defaultdict
from pathlib import Path

from tournament import AGENTS, run_match


def load_manifest(path):
    return json.loads(path.read_text(encoding="utf-8"))


def new_candidate_summary():
    return {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "errors": 0,
        "production_delta": 0,
        "ship_delta": 0,
        "loss_seeds": [],
    }


def add_candidate_result(summary, record, candidate_side):
    result = record["result"]
    final = record["final"]
    candidate_owner = "0" if candidate_side == "a" else "1"
    opponent_owner = "1" if candidate_side == "a" else "0"

    summary["games"] += 1
    summary["production_delta"] += (
        final[candidate_owner]["production"] - final[opponent_owner]["production"]
    )
    summary["ship_delta"] += (
        final[candidate_owner]["total_ships"] - final[opponent_owner]["total_ships"]
    )

    candidate_won = (
        result == "A_WIN" and candidate_side == "a"
    ) or (
        result == "B_WIN" and candidate_side == "b"
    )
    candidate_lost = (
        result == "B_WIN" and candidate_side == "a"
    ) or (
        result == "A_WIN" and candidate_side == "b"
    )

    if candidate_won:
        summary["wins"] += 1
    elif candidate_lost:
        summary["losses"] += 1
        summary["loss_seeds"].append(record["seed"])
    elif result == "DRAW":
        summary["draws"] += 1
    else:
        summary["errors"] += 1


def print_candidate_summary(summaries):
    rows = []

    for candidate, summary in summaries.items():
        resolved_games = summary["games"] - summary["errors"]
        winrate = summary["wins"] / resolved_games if resolved_games else 0.0
        avg_production_delta = (
            summary["production_delta"] / summary["games"] if summary["games"] else 0.0
        )
        avg_ship_delta = summary["ship_delta"] / summary["games"] if summary["games"] else 0.0
        rows.append(
            (
                winrate,
                avg_production_delta,
                avg_ship_delta,
                candidate,
                summary,
            )
        )

    rows.sort(reverse=True)

    print(
        "candidate,games,wins,losses,draws,errors,winrate,"
        "avg_final_production_delta,avg_final_ship_delta,loss_seeds"
    )
    for winrate, avg_production_delta, avg_ship_delta, candidate, summary in rows:
        loss_seeds = ";".join(map(str, summary["loss_seeds"][:16]))
        print(
            ",".join(
                [
                    candidate,
                    str(summary["games"]),
                    str(summary["wins"]),
                    str(summary["losses"]),
                    str(summary["draws"]),
                    str(summary["errors"]),
                    f"{winrate:.3f}",
                    f"{avg_production_delta:.1f}",
                    f"{avg_ship_delta:.1f}",
                    loss_seeds,
                ]
            )
        )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("agents/generated/manifest.json"),
    )
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument(
        "--opponents",
        nargs="+",
        default=["main", "production_hunter"],
    )
    parser.add_argument("--candidates", nargs="+")
    parser.add_argument(
        "--telemetry",
        type=Path,
        default=Path("telemetry/generated_ladder.jsonl"),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    candidates = load_manifest(args.manifest)
    if args.candidates:
        unknown_candidates = [name for name in args.candidates if name not in candidates]
        if unknown_candidates:
            raise SystemExit(f"unknown candidate(s): {', '.join(unknown_candidates)}")
        candidates = {name: candidates[name] for name in args.candidates}

    opponents = {name: AGENTS[name] for name in args.opponents}
    summaries = defaultdict(new_candidate_summary)
    seeds = range(args.seed_start, args.seed_start + args.seeds)

    args.telemetry.parent.mkdir(parents=True, exist_ok=True)
    with args.telemetry.open("w", encoding="utf-8") as telemetry_file:
        for candidate_name, candidate_path in candidates.items():
            for opponent_name, opponent_path in opponents.items():
                for seed in seeds:
                    record = run_match(
                        candidate_path,
                        opponent_path,
                        seed,
                        names=(candidate_name, opponent_name),
                    )
                    record["candidate"] = candidate_name
                    record["opponent"] = opponent_name
                    record["candidate_side"] = "a"
                    add_candidate_result(summaries[candidate_name], record, "a")
                    telemetry_file.write(json.dumps(record, sort_keys=True) + "\n")

                    record = run_match(
                        opponent_path,
                        candidate_path,
                        seed,
                        names=(opponent_name, candidate_name),
                    )
                    record["candidate"] = candidate_name
                    record["opponent"] = opponent_name
                    record["candidate_side"] = "b"
                    add_candidate_result(summaries[candidate_name], record, "b")
                    telemetry_file.write(json.dumps(record, sort_keys=True) + "\n")

    print_candidate_summary(summaries)


if __name__ == "__main__":
    main()
