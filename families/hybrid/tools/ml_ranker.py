import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, VotingRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[0]

PARAM_BOUNDS = {
    "min_ships": (4, 20),
    "min_reserve": (2, 20),
    "reserve_prod_mult": (1.5, 6.0),
    "panic_reserve_mult": (0.0, 1.8),
    "neutral_bonus": (0, 32),
    "neutral_tax": (0, 24),
    "enemy_bonus": (18, 76),
    "enemy_weak_bonus": (0.0, 4.0),
    "counter_bonus": (0, 42),
    "pressure_max": (0, 95),
    "pressure_divisor": (6, 80),
    "production_weight": (8, 48),
    "high_production_weight": (14, 60),
    "high_prod_tax": (0, 42),
    "distance_weight": (1.35, 4.2),
    "high_distance_weight": (1.1, 3.8),
    "short_hop_bonus": (0.0, 3.8),
    "short_hop_range": (16, 52),
    "ship_weight": (0.55, 2.45),
    "high_ship_weight": (0.5, 2.35),
    "overkill": (0, 8),
    "high_prod_extra": (0, 5),
    "enemy_extra": (0, 14),
    "attack_fraction": (0.22, 0.98),
    "max_attacks_per_turn": (1, 10),
    "comet_bonus": (-8, 18),
    "staging_penalty": (5.0, 35.0),
    "defense_worth_factor": (4.0, 20.0),
    "counter_attack_bonus": (5.0, 45.0),
    "production_forecast_mult": (0.0, 2.0),
    "evac_eta_threshold": (1.5, 6.0),
    "evac_minor_prod": (1, 3),
    "sync_max_eta": (4.0, 20.0),
    "sync_min_target_prod": (1, 5),
    "sync_min_target_ships": (15, 60),
    "snipe_max_step": (40, 180),
    "snipe_overkill": (1, 8),
    "honeypot_min_prod": (2, 5),
    "honeypot_reserve": (2, 10),
    "feint_interval": (4, 15),
    "feint_min_margin": (1, 5),
}

PARAM_NAMES = list(PARAM_BOUNDS)
DEFAULT_PRIORS_PATH = Path("training/adaptive_priors.json")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def normalized_param(params, name):
    low, high = PARAM_BOUNDS[name]
    value = params.get(name, (low + high) / 2.0)
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = (low + high) / 2.0
    value = max(low, min(high, value))
    return (value - low) / (high - low)


def base_family(base):
    if not base:
        return "unknown"
    if base in ("champion_template", "cw_champion_template") or base.endswith("_champion_template"):
        return "champion_template"
    if "replay" in base:
        return "replay"
    if base.startswith("gen_"):
        return "generated"
    if base.startswith("cw_"):
        return "counterwave"
    if base.startswith("elite_"):
        return "elite"
    if base == "manual":
        return "manual"
    return "other"


def load_adaptive_priors(path=DEFAULT_PRIORS_PATH):
    path = REPO_ROOT / path
    if not path.exists():
        return {}
    try:
        priors = load_json(path)
    except (OSError, json.JSONDecodeError):
        return {}
    if not priors.get("enabled"):
        return {}
    return priors


def prior_for(priors, name):
    prior = (priors or {}).get("parameters", {}).get(name)
    if prior and prior.get("direction") in ("up", "down"):
        return prior
    return None


def feature_dict(params, base, priors=None):
    features = {}
    raw = {}
    prior_alignment = 0.0
    prior_confidence_total = 0.0
    prior_in_band = 0.0
    for name in PARAM_NAMES:
        low, high = PARAM_BOUNDS[name]
        value = params.get(name, (low + high) / 2.0)
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = (low + high) / 2.0
        value = max(low, min(high, value))
        raw[name] = value
        normalized = (value - low) / (high - low)
        features[f"param:{name}"] = normalized

        prior = prior_for(priors, name)
        if prior:
            direction = 1.0 if prior["direction"] == "up" else -1.0
            confidence = float(prior.get("confidence", 0.0))
            good_low = float(prior.get("good_low", low))
            good_high = float(prior.get("good_high", high))
            good_avg = float(prior.get("good_avg", (good_low + good_high) / 2.0))
            good_low_norm = (max(low, min(high, good_low)) - low) / (high - low)
            good_high_norm = (max(low, min(high, good_high)) - low) / (high - low)
            good_avg_norm = (max(low, min(high, good_avg)) - low) / (high - low)
            in_band = 1.0 if good_low <= value <= good_high else 0.0
            distance_to_good = abs(normalized - good_avg_norm)

            features[f"prior:{name}:direction"] = direction
            features[f"prior:{name}:confidence"] = confidence
            features[f"prior:{name}:in_good_band"] = in_band
            features[f"prior:{name}:distance_to_good"] = distance_to_good * confidence
            features[f"prior:{name}:signed_value"] = normalized * direction * confidence
            features[f"prior:{name}:good_low"] = good_low_norm
            features[f"prior:{name}:good_high"] = good_high_norm

            prior_alignment += (1.0 - distance_to_good) * confidence
            prior_confidence_total += confidence
            prior_in_band += in_band * confidence

    features["gap:production"] = features["param:high_production_weight"] - features["param:production_weight"]
    features["gap:distance"] = features["param:distance_weight"] - features["param:high_distance_weight"]
    features["gap:ship"] = features["param:ship_weight"] - features["param:high_ship_weight"]
    features["balance:enemy_neutral"] = features["param:enemy_bonus"] - features["param:neutral_bonus"]
    features["pressure_combo"] = features["param:pressure_max"] * features["param:enemy_bonus"]
    features["reserve_combo"] = features["param:min_reserve"] * features["param:reserve_prod_mult"]
    features["counterwave:turtle_posture"] = (
        features["param:min_reserve"]
        + features["param:reserve_prod_mult"]
        + features["param:panic_reserve_mult"]
    ) / 3.0
    features["counterwave:anti_neutral"] = features["param:neutral_tax"] - features["param:neutral_bonus"]
    features["counterwave:enemy_pressure"] = (
        features["param:enemy_bonus"]
        + features["param:enemy_weak_bonus"]
        + features["param:counter_bonus"]
    ) / 3.0
    features["counterwave:short_hop"] = (
        features["param:short_hop_bonus"] + features["param:short_hop_range"]
    ) / 2.0

    family = base_family(base)
    features[f"family:{family}"] = 1.0
    if family != "elite":
        features[f"base:{base}"] = 1.0
    if "champion_template" in base:
        features["contains:champion_template"] = 1.0
    if "cw_champion_template" in base:
        features["contains:cw_champion_template"] = 1.0
    if "replay_early" in base:
        features["contains:replay_early"] = 1.0
    if "replay_mid" in base:
        features["contains:replay_mid"] = 1.0
    if "replay_late" in base:
        features["contains:replay_late"] = 1.0
    if "target_enemy" in base:
        features["contains:target_enemy"] = 1.0
    if "target_neutral" in base:
        features["contains:target_neutral"] = 1.0
    if "counter" in base:
        features["contains:counter"] = 1.0
    if "raid" in base:
        features["contains:raid"] = 1.0
    if "fortress" in base:
        features["contains:fortress"] = 1.0

    if prior_confidence_total:
        features["prior:alignment"] = prior_alignment / prior_confidence_total
        features["prior:in_good_band_ratio"] = prior_in_band / prior_confidence_total
        features["prior:confidence_total"] = prior_confidence_total / max(1, len(PARAM_NAMES))

    return features


def quality_from_summary(summary):
    winrate = float(summary.get("winrate", 0.0))
    score = float(summary.get("score", winrate))
    return winrate * 0.7 + score * 0.3


def collect_training_rows(output_dir=Path("runs"), min_games=20, max_rounds=None):
    output_dir = REPO_ROOT / output_dir
    reports = sorted(
        output_dir.glob("round_*/round_report.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if max_rounds:
        reports = reports[-max_rounds:]

    rows = []
    for report_path in reports:
        candidates_path = report_path.parent / "candidates.json"
        if not candidates_path.exists():
            continue

        try:
            report = load_json(report_path)
            candidates = load_json(candidates_path)
        except (OSError, json.JSONDecodeError):
            continue

        candidate_by_name = {candidate.get("name"): candidate for candidate in candidates}
        for result in report.get("validated_finalists", []):
            summary = result.get("summary", {})
            games = int(summary.get("games", 0))
            if games < min_games:
                continue

            candidate = candidate_by_name.get(result.get("candidate"))
            if not candidate:
                continue

            params = candidate.get("params", {})
            if not params:
                continue

            winrate = float(summary.get("winrate", 0.0))
            score = float(summary.get("score", winrate))
            rows.append(
                {
                    "round": report.get("round"),
                    "round_dir": str(report_path.parent),
                    "candidate": candidate["name"],
                    "base": candidate.get("base", "unknown"),
                    "params": params,
                    "games": games,
                    "wins": int(summary.get("wins", 0)),
                    "losses": int(summary.get("losses", 0)),
                    "winrate": winrate,
                    "score": score,
                    "quality": quality_from_summary(summary),
                    "passed": bool(result.get("passed")),
                    "reason": result.get("reason", ""),
                    "avg_production_delta": float(summary.get("avg_production_delta", 0.0)),
                    "avg_ship_delta": float(summary.get("avg_ship_delta", 0.0)),
                }
            )

    return rows


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True) + "\n")


def load_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def source_discount(row):
    """Discount weight for data from non-native sources.

    Hybrid's own rounds → 1.0 (same engine, correct opponents)
    Counterwave data    → 0.6 (same engine, different opponents)
    Root data           → 0.3 (different engine, rough directional signal)
    """
    source = row.get("source", "")
    base = row.get("base", "")
    round_dir = str(row.get("round_dir", ""))

    # Cross-family tournament data
    if source == "cross_family_tournament" or round_dir == "cross_family_tournament":
        if "root" in base:
            return 0.3
        return 0.6

    # Merged dataset rows (no source field) — infer from base name
    if "cw_" in base or "counterwave" in base:
        # If it has no round (came from counterwave family merge)
        if row.get("round", -1) == 0 or "counterwave" in round_dir:
            return 0.6

    # Everything else is hybrid-native
    return 1.0


def build_training_arrays(rows, priors=None):
    vectorizer = DictVectorizer(sparse=False)
    feature_rows = [feature_dict(row["params"], row.get("base", "unknown"), priors) for row in rows]
    x = vectorizer.fit_transform(feature_rows)
    y = np.array([row["quality"] for row in rows], dtype=float)
    sample_weight = np.array(
        [
            max(0.35, min(2.0, float(row.get("games", 0)) / 60.0))
            * source_discount(row)
            for row in rows
        ],
        dtype=float,
    )
    return vectorizer, x, y, sample_weight


def new_model(random_state=42):
    trees = ExtraTreesRegressor(
        n_estimators=420,
        min_samples_leaf=2,
        random_state=random_state,
        n_jobs=-1,
    )
    forest = RandomForestRegressor(
        n_estimators=220,
        min_samples_leaf=2,
        random_state=random_state + 17,
        n_jobs=-1,
    )
    return VotingRegressor([("extra", trees), ("forest", forest)], n_jobs=-1)


def train_ranker(
    output_dir=Path("runs"),
    dataset_path=Path("training/ml_dataset.jsonl"),
    model_path=Path("training/ml_ranker.joblib"),
    min_games=10,
    min_samples=40,
    max_rounds=None,
    random_state=42,
    priors_path=DEFAULT_PRIORS_PATH,
):
    rows = collect_training_rows(output_dir=output_dir, min_games=min_games, max_rounds=max_rounds)
    dataset_path = REPO_ROOT / dataset_path
    model_path = REPO_ROOT / model_path

    # Also load pre-existing dataset rows (from merge_datasets.py or cross_family_tournament.py)
    # This ensures bootstrapped data is always available even before hybrid runs its own rounds.
    if dataset_path.exists():
        existing_rows = load_jsonl(dataset_path)
        existing_candidates = {row.get("candidate") for row in existing_rows if row.get("candidate")}
        round_candidates = {row.get("candidate") for row in rows if row.get("candidate")}
        # Add existing rows that aren't already covered by round reports
        for row in existing_rows:
            if row.get("candidate") and row["candidate"] not in round_candidates:
                if row.get("params") and int(row.get("games", 0)) >= min_games:
                    rows.append(row)

    write_jsonl(dataset_path, rows)

    if len(rows) < min_samples:
        metadata = {
            "trained": False,
            "reason": f"not enough samples: {len(rows)} < {min_samples}",
            "samples": len(rows),
            "dataset_path": str(dataset_path),
            "model_path": str(model_path),
        }
        save_json(model_path.with_suffix(".metadata.json"), metadata)
        return metadata

    priors = load_adaptive_priors(priors_path)
    vectorizer, x, y, sample_weight = build_training_arrays(rows, priors)
    holdout = {}
    if len(rows) >= 60:
        (
            x_train,
            x_test,
            y_train,
            y_test,
            weights_train,
            _weights_test,
        ) = train_test_split(x, y, sample_weight, test_size=0.22, random_state=random_state)
        probe_model = new_model(random_state=random_state)
        probe_model.fit(x_train, y_train, sample_weight=weights_train)
        predictions = probe_model.predict(x_test)
        holdout = {
            "mae": round(float(mean_absolute_error(y_test, predictions)), 4),
            "r2": round(float(r2_score(y_test, predictions)), 4),
            "samples": len(y_test),
        }

    model = new_model(random_state=random_state)
    model.fit(x, y, sample_weight=sample_weight)

    payload = {
        "model": model,
        "vectorizer": vectorizer,
        "metadata": {
            "trained": True,
            "samples": len(rows),
            "features": len(vectorizer.feature_names_),
            "dataset_path": str(dataset_path),
            "model_path": str(model_path),
            "holdout": holdout,
            "target": "quality = winrate * 0.7 + score * 0.3",
            "sklearn_version": sklearn.__version__,
            "priors_path": str(REPO_ROOT / priors_path),
            "priors_enabled": bool(priors),
            "priors_parameter_count": len(priors.get("parameters", {})),
        },
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, model_path)
    save_json(model_path.with_suffix(".metadata.json"), payload["metadata"])
    return payload["metadata"]


def load_ranker(model_path=Path("training/ml_ranker.joblib")):
    model_path = REPO_ROOT / model_path
    if not model_path.exists():
        return None
    return joblib.load(model_path)


def score_candidate_records(records, model_path=Path("training/ml_ranker.joblib"), priors_path=DEFAULT_PRIORS_PATH):
    payload = load_ranker(model_path)
    if not payload:
        return []

    priors = load_adaptive_priors(priors_path)
    vectorizer = payload["vectorizer"]
    model = payload["model"]
    feature_rows = [
        feature_dict(record.get("params", {}), record.get("base", "unknown"), priors)
        for record in records
    ]
    x = vectorizer.transform(feature_rows)
    predictions = model.predict(x)
    scored = []
    for record, prediction in zip(records, predictions):
        item = dict(record)
        item["ml_score"] = round(float(prediction), 6)
        item["ml_model_samples"] = int(payload["metadata"].get("samples", 0))
        scored.append(item)
    return scored


def rank_candidate_records(records, model_path=Path("training/ml_ranker.joblib"), priors_path=DEFAULT_PRIORS_PATH):
    scored = score_candidate_records(records, model_path=model_path, priors_path=priors_path)
    return sorted(scored, key=lambda item: item.get("ml_score", -999.0), reverse=True)


def summarize_rows(rows):
    if not rows:
        return {"samples": 0}
    winrates = [row["winrate"] for row in rows]
    qualities = [row["quality"] for row in rows]
    return {
        "samples": len(rows),
        "avg_winrate": round(float(np.mean(winrates)), 4),
        "best_winrate": round(float(np.max(winrates)), 4),
        "avg_quality": round(float(np.mean(qualities)), 4),
        "best_quality": round(float(np.max(qualities)), 4),
        "passed": sum(1 for row in rows if row.get("passed")),
    }


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    dataset = subparsers.add_parser("dataset")
    dataset.add_argument("--output-dir", type=Path, default=Path("runs"))
    dataset.add_argument("--dataset-path", type=Path, default=Path("training/ml_dataset.jsonl"))
    dataset.add_argument("--min-games", type=int, default=10)
    dataset.add_argument("--max-rounds", type=int, default=None)

    train = subparsers.add_parser("train")
    train.add_argument("--output-dir", type=Path, default=Path("runs"))
    train.add_argument("--dataset-path", type=Path, default=Path("training/ml_dataset.jsonl"))
    train.add_argument("--model-path", type=Path, default=Path("training/ml_ranker.joblib"))
    train.add_argument("--min-games", type=int, default=10)
    train.add_argument("--min-samples", type=int, default=40)
    train.add_argument("--max-rounds", type=int, default=None)
    train.add_argument("--random-state", type=int, default=42)
    train.add_argument("--priors-path", type=Path, default=DEFAULT_PRIORS_PATH)

    score = subparsers.add_parser("score")
    score.add_argument("candidates", type=Path)
    score.add_argument("--model-path", type=Path, default=Path("training/ml_ranker.joblib"))
    score.add_argument("--priors-path", type=Path, default=DEFAULT_PRIORS_PATH)
    score.add_argument("--top", type=int, default=20)

    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "dataset":
        rows = collect_training_rows(
            output_dir=args.output_dir,
            min_games=args.min_games,
            max_rounds=args.max_rounds,
        )
        write_jsonl(REPO_ROOT / args.dataset_path, rows)
        print(json.dumps(summarize_rows(rows), indent=2, sort_keys=True))
        return

    if args.command == "train":
        metadata = train_ranker(
            output_dir=args.output_dir,
            dataset_path=args.dataset_path,
            model_path=args.model_path,
            min_games=args.min_games,
            min_samples=args.min_samples,
            max_rounds=args.max_rounds,
            random_state=args.random_state,
            priors_path=args.priors_path,
        )
        print(json.dumps(metadata, indent=2, sort_keys=True))
        return

    if args.command == "score":
        candidates = load_json(REPO_ROOT / args.candidates)
        ranked = rank_candidate_records(candidates, model_path=args.model_path, priors_path=args.priors_path)
        for item in ranked[: args.top]:
            print(f"{item['name']}: ml_score={item['ml_score']:.4f} base={item.get('base')}")


if __name__ == "__main__":
    main()
