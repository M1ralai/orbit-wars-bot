import json
from pathlib import Path

# Paths
runs_dir = Path("/Users/atahandemirer/Developer/orbit-wars-bot/families/hybrid/runs")
telemetry_dir = Path("/Users/atahandemirer/Developer/orbit-wars-bot/families/hybrid/telemetry")

# Target run: round_0004_20260523_123310
target_run_dir = runs_dir / "round_0004_20260523_123310"
report_path = target_run_dir / "round_report.json"
candidates_path = target_run_dir / "candidates.json"
smoke_path = telemetry_dir / "round_0004_smoke.jsonl"

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

def main():
    if not report_path.exists():
        print(f"Report does not exist: {report_path}")
        return
    if not candidates_path.exists():
        print(f"Candidates does not exist: {candidates_path}")
        return
    if not smoke_path.exists():
        print(f"Smoke telemetry does not exist: {smoke_path}")
        return

    # Load candidates
    with candidates_path.open("r", encoding="utf-8") as f:
        candidates = json.load(f)

    # Prepare candidate map and summaries
    candidate_summaries = {c["name"]: new_summary(c["name"]) for c in candidates}

    # Load smoke telemetry
    with smoke_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            candidate_name = record["candidate"]
            if candidate_name in candidate_summaries:
                add_result(
                    candidate_summaries[candidate_name],
                    record,
                    record["candidate_side"],
                    record["opponent"]
                )

    # Load report
    with report_path.open("r", encoding="utf-8") as f:
        report = json.load(f)

    # Format gate results
    gate_results = []
    smoke_threshold = 0.63
    for candidate in candidates:
        summary = candidate_summaries[candidate["name"]]
        gate_results.append(
            {
                "candidate": candidate["name"],
                "passed": False,
                "reason": f"failed smoke test (winrate {winrate(summary):.3f} < {smoke_threshold:.2f})",
                "summary": compact_summary(summary),
            }
        )

    report["validated_finalists"] = gate_results
    
    # Save report
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    
    print(f"Successfully rebuilt round report for round 4! Injected {len(gate_results)} candidates into validated_finalists.")

if __name__ == "__main__":
    main()
