import argparse
import json
from pathlib import Path


def build_template():
    bot_dir = Path(__file__).resolve().parent.parent / "bot"
    order = ["params.py", "geometry.py", "state.py", "scoring.py", "strategy.py"]
    lines = ["import math"]
    
    for filename in order:
        content = (bot_dir / filename).read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("import math") or line.startswith("from bot.") or line.startswith("import bot."):
                continue
            lines.append(line)
            
    raw_text = "\n".join(lines)
    
    # Escape braces so .format(**params) works correctly
    text = raw_text.replace("{", "{{").replace("}", "}}")
    
    # Unescape the known injected parameters
    known_params = [
        "min_ships", "min_reserve", "reserve_prod_mult", "neutral_bonus", 
        "enemy_bonus", "pressure_max", "pressure_divisor", "production_weight", 
        "high_production_weight", "distance_weight", "high_distance_weight", 
        "ship_weight", "high_ship_weight", "overkill", "high_prod_extra", "enemy_extra"
    ]
    for p in known_params:
        text = text.replace(f"{{{{{p}}}}}", f"{{{p}}}")
        
    return text

TEMPLATE = build_template()


CANDIDATES = {
    "gen_balanced_claim": {
        "min_ships": 12,
        "min_reserve": 5,
        "reserve_prod_mult": 3.0,
        "neutral_bonus": 8,
        "enemy_bonus": 16,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 35,
        "high_production_weight": 40,
        "distance_weight": 2.15,
        "high_distance_weight": 1.95,
        "ship_weight": 1.4,
        "high_ship_weight": 1.25,
        "overkill": 2,
        "high_prod_extra": 0,
        "enemy_extra": 0,
    },
    "gen_eco_light": {
        "min_ships": 12,
        "min_reserve": 5,
        "reserve_prod_mult": 3.0,
        "neutral_bonus": 10,
        "enemy_bonus": 14,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 36,
        "high_production_weight": 48,
        "distance_weight": 2.15,
        "high_distance_weight": 1.75,
        "ship_weight": 1.35,
        "high_ship_weight": 1.15,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 0,
    },
    "gen_eco_commit": {
        "min_ships": 11,
        "min_reserve": 4,
        "reserve_prod_mult": 2.7,
        "neutral_bonus": 12,
        "enemy_bonus": 16,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 34,
        "high_production_weight": 55,
        "distance_weight": 2.05,
        "high_distance_weight": 1.6,
        "ship_weight": 1.3,
        "high_ship_weight": 1.05,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 1,
    },
    "gen_tempo_enemy": {
        "min_ships": 12,
        "min_reserve": 5,
        "reserve_prod_mult": 2.8,
        "neutral_bonus": 8,
        "enemy_bonus": 26,
        "pressure_max": 16,
        "pressure_divisor": 24,
        "production_weight": 34,
        "high_production_weight": 44,
        "distance_weight": 2.1,
        "high_distance_weight": 1.8,
        "ship_weight": 1.3,
        "high_ship_weight": 1.1,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 3,
    },
    "gen_fast_expand": {
        "min_ships": 9,
        "min_reserve": 4,
        "reserve_prod_mult": 2.4,
        "neutral_bonus": 13,
        "enemy_bonus": 12,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 38,
        "high_production_weight": 48,
        "distance_weight": 1.95,
        "high_distance_weight": 1.65,
        "ship_weight": 1.25,
        "high_ship_weight": 1.05,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 0,
    },
    "gen_safe_expand": {
        "min_ships": 14,
        "min_reserve": 7,
        "reserve_prod_mult": 3.7,
        "neutral_bonus": 10,
        "enemy_bonus": 14,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 37,
        "high_production_weight": 47,
        "distance_weight": 2.0,
        "high_distance_weight": 1.7,
        "ship_weight": 1.45,
        "high_ship_weight": 1.25,
        "overkill": 2,
        "high_prod_extra": 0,
        "enemy_extra": 0,
    },
    "gen_enemy_snipe": {
        "min_ships": 13,
        "min_reserve": 5,
        "reserve_prod_mult": 3.0,
        "neutral_bonus": 6,
        "enemy_bonus": 34,
        "pressure_max": 22,
        "pressure_divisor": 18,
        "production_weight": 32,
        "high_production_weight": 43,
        "distance_weight": 2.0,
        "high_distance_weight": 1.75,
        "ship_weight": 1.2,
        "high_ship_weight": 1.05,
        "overkill": 3,
        "high_prod_extra": 1,
        "enemy_extra": 5,
    },
    "gen_low_cost": {
        "min_ships": 10,
        "min_reserve": 4,
        "reserve_prod_mult": 2.6,
        "neutral_bonus": 9,
        "enemy_bonus": 18,
        "pressure_max": 10,
        "pressure_divisor": 30,
        "production_weight": 35,
        "high_production_weight": 43,
        "distance_weight": 2.15,
        "high_distance_weight": 1.85,
        "ship_weight": 1.05,
        "high_ship_weight": 0.95,
        "overkill": 2,
        "high_prod_extra": 0,
        "enemy_extra": 1,
    },
}


def write_candidate(name, params, output_dir):
    output_path = output_dir / f"{name}.py"
    output_path.write_text(TEMPLATE.format(**params), encoding="utf-8")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("agents/generated"))
    return parser.parse_args()


def main():
    args = parse_args()
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
