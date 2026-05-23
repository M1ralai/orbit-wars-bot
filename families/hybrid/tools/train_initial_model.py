import sys
from pathlib import Path
import joblib
import sklearn

# Add current directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ml_ranker import load_jsonl, build_training_arrays, new_model, save_json, REPO_ROOT

def main():
    dataset_path = SCRIPT_DIR.parent / "training" / "ml_dataset.jsonl"
    model_path = SCRIPT_DIR.parent / "training" / "ml_ranker.joblib"
    metadata_path = SCRIPT_DIR.parent / "training" / "ml_ranker.metadata.json"

    print(f"Loading merged dataset from {dataset_path}...")
    rows = load_jsonl(dataset_path)
    if not rows:
        print("Error: No data rows found to train on.")
        sys.exit(1)

    print(f"Loaded {len(rows)} training rows.")

    # Build arrays
    print("Building training arrays and features...")
    vectorizer, x, y, sample_weight = build_training_arrays(rows, priors=None)

    # Train model
    print("Training combined VotingRegressor model...")
    model = new_model(random_state=42)
    model.fit(x, y, sample_weight=sample_weight)

    # Save payload
    metadata = {
        "trained": True,
        "samples": len(rows),
        "features": len(vectorizer.feature_names_),
        "dataset_path": str(dataset_path),
        "model_path": str(model_path),
        "target": "quality = winrate * 0.7 + score * 0.3",
        "sklearn_version": sklearn.__version__,
        "priors_enabled": False,
    }

    payload = {
        "model": model,
        "vectorizer": vectorizer,
        "metadata": metadata,
    }

    print(f"Saving ML model to {model_path}...")
    joblib.dump(payload, model_path)
    save_json(metadata_path, metadata)
    print("Initial ML Ranker training completed successfully!")

if __name__ == "__main__":
    main()
