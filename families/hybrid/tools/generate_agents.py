import argparse
import json
from pathlib import Path


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
    "comet_bonus",
}

PARAM_BOUNDS = {
    "min_ships": (3, 26),
    "min_reserve": (1, 22),
    "reserve_prod_mult": (1.0, 7.0),
    "neutral_bonus": (0, 40),
    "enemy_bonus": (14, 86),
    "pressure_max": (0, 110),
    "pressure_divisor": (5, 90),
    "production_weight": (6, 64),
    "high_production_weight": (10, 78),
    "distance_weight": (1.0, 5.0),
    "high_distance_weight": (0.8, 4.5),
    "ship_weight": (0.4, 3.0),
    "high_ship_weight": (0.3, 2.8),
    "overkill": (0, 10),
    "high_prod_extra": (0, 7),
    "enemy_extra": (0, 18),
    "comet_bonus": (-10, 24),
    "production_forecast_mult": (0.0, 2.5),
}


def build_template():
    bot_dir = Path(__file__).resolve().parent.parent / "bot"
    order = [
        "params.py",
        "geometry.py",
        "state.py",
        "scoring.py",
        "strategies/helpers.py",
        "strategies/stance.py",
        "strategies/evacuation.py",
        "strategies/snipe.py",
        "strategies/reinforce.py",
        "strategies/sync.py",
        "strategies/honeypot.py",
        "strategies/counter_punch.py",
        "strategies/chain_expand.py",
        "strategies/prod_starve.py",
        "strategies/vulture.py",
        "strategies/turtle.py",
        "strategies/overflow.py",
        "strategies/comet_rush.py",
        "strategies/core_attack.py",
        "strategy.py",
    ]
    lines = ["import math"]

    for filename in order:
        content = (bot_dir / filename).read_text(encoding="utf-8")
        skip_import_block = False
        for line in content.splitlines():
            if skip_import_block:
                if line.strip() == ")":
                    skip_import_block = False
                continue
            if (
                line.startswith("import math")
                or line.startswith("from bot.")
                or line.startswith("import bot.")
            ):
                if line.rstrip().endswith("("):
                    skip_import_block = True
                continue
            lines.append(line)

    raw_text = "\n".join(lines)
    text = raw_text.replace("{", "{{").replace("}", "}}")
    for name in PARAM_BOUNDS:
        text = text.replace(f"{{{{{name}}}}}", f"{{{name}}}")
    return text


TEMPLATE = build_template()


CANDIDATES = {
    "hybrid_baseline": {
        "min_ships": 14,
        "min_reserve": 4,
        "reserve_prod_mult": 2.4,
        "neutral_bonus": 22,
        "enemy_bonus": 34,
        "pressure_max": 16,
        "pressure_divisor": 32,
        "production_weight": 34,
        "high_production_weight": 50,
        "distance_weight": 2.35,
        "high_distance_weight": 2.0,
        "ship_weight": 1.05,
        "high_ship_weight": 0.85,
        "overkill": 3,
        "high_prod_extra": 2,
        "enemy_extra": 9,
        "comet_bonus": 10,
        "production_forecast_mult": 0.5,
    },
}


def write_candidate(name, params, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}.py"
    output_path.write_text(TEMPLATE.format(**params), encoding="utf-8")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("agents/generated"))
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.output_dir.is_absolute():
        args.output_dir = Path(__file__).resolve().parent.parent / args.output_dir
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    for name, params in CANDIDATES.items():
        output_path = write_candidate(name, params, args.output_dir)
        manifest[name] = str(output_path)

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    for name, path in manifest.items():
        print(f"{name}={path}")


if __name__ == "__main__":
    main()
