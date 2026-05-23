import json
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ROOT_DATASET_PATH = REPO_ROOT / "training" / "ml_dataset.jsonl"
CW_DATASET_PATH = REPO_ROOT / "families" / "counterwave" / "training" / "ml_dataset.jsonl"
HYBRID_DATASET_PATH = REPO_ROOT / "families" / "hybrid" / "training" / "ml_dataset.jsonl"

# Mapping default values for missing keys from 16-param space to 26-param space
MAPPING_DEFAULTS = {
    "panic_reserve_mult": 0.0,
    "neutral_tax": 0,
    "enemy_weak_bonus": 0.0,
    "counter_bonus": 0,
    "high_prod_tax": 0,
    "short_hop_bonus": 0.0,
    "short_hop_range": 16,
    "attack_fraction": 0.95,
    "max_attacks_per_turn": 8,
}

def merge():
    HYBRID_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = []

    # 1. Read Root Dataset (16 parameters) and translate to 26 parameters
    if ROOT_DATASET_PATH.exists():
        print(f"Reading root dataset from {ROOT_DATASET_PATH}...")
        with open(ROOT_DATASET_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if "params" in data and "source" not in data["params"]:
                    # Translate params
                    params = data["params"]
                    for k, val in MAPPING_DEFAULTS.items():
                        if k not in params:
                            params[k] = val
                    if "comet_bonus" not in params:
                        params["comet_bonus"] = 10
                    data["params"] = params
                records.append(data)
        print(f"Loaded {len(records)} translated records from root.")

    # 2. Read Counterwave Dataset (26 parameters)
    cw_count = 0
    if CW_DATASET_PATH.exists():
        print(f"Reading counterwave dataset from {CW_DATASET_PATH}...")
        with open(CW_DATASET_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                records.append(data)
                cw_count += 1
        print(f"Loaded {cw_count} records from counterwave.")

    # 3. Write Hybrid Dataset
    print(f"Writing {len(records)} total records to {HYBRID_DATASET_PATH}...")
    with open(HYBRID_DATASET_PATH, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    print("Merge complete successfully!")

if __name__ == "__main__":
    merge()
