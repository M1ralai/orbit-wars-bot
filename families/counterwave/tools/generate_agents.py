import argparse
import json
from pathlib import Path


INT_PARAMS = {
    "min_ships",
    "min_reserve",
    "neutral_bonus",
    "neutral_tax",
    "enemy_bonus",
    "counter_bonus",
    "pressure_max",
    "pressure_divisor",
    "production_weight",
    "high_production_weight",
    "high_prod_tax",
    "short_hop_range",
    "overkill",
    "high_prod_extra",
    "enemy_extra",
    "max_attacks_per_turn",
    "comet_bonus",
}

PARAM_BOUNDS = {
    "min_ships": (4, 16),
    "min_reserve": (6, 28),
    "reserve_prod_mult": (3.0, 8.0),
    "panic_reserve_mult": (0.6, 2.4),
    "neutral_bonus": (-12, 16),
    "neutral_tax": (0, 36),
    "enemy_bonus": (18, 76),
    "enemy_weak_bonus": (0.0, 4.0),
    "counter_bonus": (0, 42),
    "pressure_max": (12, 95),
    "pressure_divisor": (6, 80),
    "production_weight": (8, 36),
    "high_production_weight": (14, 46),
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
    "attack_fraction": (0.22, 0.82),
    "max_attacks_per_turn": (1, 5),
    "comet_bonus": (-8, 18),
}


def build_template():
    bot_dir = Path(__file__).resolve().parent.parent / "bot"
    order = ["params.py", "geometry.py", "state.py", "scoring.py", "strategy.py"]
    lines = ["import math"]

    for filename in order:
        content = (bot_dir / filename).read_text(encoding="utf-8")
        for line in content.splitlines():
            if (
                line.startswith("import math")
                or line.startswith("from bot.")
                or line.startswith("import bot.")
            ):
                continue
            lines.append(line)

    raw_text = "\n".join(lines)
    text = raw_text.replace("{", "{{").replace("}", "}}")
    for name in PARAM_BOUNDS:
        text = text.replace(f"{{{{{name}}}}}", f"{{{name}}}")
    return text


TEMPLATE = build_template()


CANDIDATES = {
    "cw_anchor_hold": {
        "min_ships": 11,
        "min_reserve": 16,
        "reserve_prod_mult": 5.2,
        "panic_reserve_mult": 1.4,
        "neutral_bonus": 4,
        "neutral_tax": 18,
        "enemy_bonus": 42,
        "enemy_weak_bonus": 1.2,
        "counter_bonus": 24,
        "pressure_max": 44,
        "pressure_divisor": 24,
        "production_weight": 18,
        "high_production_weight": 28,
        "high_prod_tax": 20,
        "distance_weight": 2.65,
        "high_distance_weight": 2.25,
        "short_hop_bonus": 1.8,
        "short_hop_range": 34,
        "ship_weight": 1.45,
        "high_ship_weight": 1.25,
        "overkill": 3,
        "high_prod_extra": 2,
        "enemy_extra": 6,
        "attack_fraction": 0.42,
        "max_attacks_per_turn": 2,
        "comet_bonus": 2,
    },
    "cw_low_neutral_raid": {
        "min_ships": 8,
        "min_reserve": 12,
        "reserve_prod_mult": 4.4,
        "panic_reserve_mult": 1.1,
        "neutral_bonus": -4,
        "neutral_tax": 24,
        "enemy_bonus": 54,
        "enemy_weak_bonus": 2.0,
        "counter_bonus": 16,
        "pressure_max": 60,
        "pressure_divisor": 18,
        "production_weight": 14,
        "high_production_weight": 24,
        "high_prod_tax": 28,
        "distance_weight": 2.2,
        "high_distance_weight": 1.95,
        "short_hop_bonus": 2.4,
        "short_hop_range": 42,
        "ship_weight": 1.05,
        "high_ship_weight": 0.95,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 4,
        "attack_fraction": 0.58,
        "max_attacks_per_turn": 3,
        "comet_bonus": -2,
    },
    "cw_counter_punch": {
        "min_ships": 13,
        "min_reserve": 20,
        "reserve_prod_mult": 6.4,
        "panic_reserve_mult": 2.0,
        "neutral_bonus": 0,
        "neutral_tax": 20,
        "enemy_bonus": 46,
        "enemy_weak_bonus": 1.4,
        "counter_bonus": 36,
        "pressure_max": 36,
        "pressure_divisor": 34,
        "production_weight": 16,
        "high_production_weight": 26,
        "high_prod_tax": 18,
        "distance_weight": 2.95,
        "high_distance_weight": 2.55,
        "short_hop_bonus": 2.2,
        "short_hop_range": 30,
        "ship_weight": 1.6,
        "high_ship_weight": 1.35,
        "overkill": 4,
        "high_prod_extra": 2,
        "enemy_extra": 8,
        "attack_fraction": 0.34,
        "max_attacks_per_turn": 2,
        "comet_bonus": 0,
    },
    "cw_edge_bleed": {
        "min_ships": 7,
        "min_reserve": 10,
        "reserve_prod_mult": 3.8,
        "panic_reserve_mult": 0.9,
        "neutral_bonus": 2,
        "neutral_tax": 12,
        "enemy_bonus": 38,
        "enemy_weak_bonus": 2.8,
        "counter_bonus": 12,
        "pressure_max": 72,
        "pressure_divisor": 12,
        "production_weight": 12,
        "high_production_weight": 22,
        "high_prod_tax": 16,
        "distance_weight": 1.9,
        "high_distance_weight": 1.7,
        "short_hop_bonus": 3.0,
        "short_hop_range": 48,
        "ship_weight": 0.85,
        "high_ship_weight": 0.75,
        "overkill": 1,
        "high_prod_extra": 1,
        "enemy_extra": 3,
        "attack_fraction": 0.68,
        "max_attacks_per_turn": 4,
        "comet_bonus": 4,
    },
    "cw_fortress": {
        "min_ships": 15,
        "min_reserve": 24,
        "reserve_prod_mult": 7.2,
        "panic_reserve_mult": 2.2,
        "neutral_bonus": 8,
        "neutral_tax": 16,
        "enemy_bonus": 36,
        "enemy_weak_bonus": 0.8,
        "counter_bonus": 40,
        "pressure_max": 28,
        "pressure_divisor": 48,
        "production_weight": 22,
        "high_production_weight": 34,
        "high_prod_tax": 12,
        "distance_weight": 3.15,
        "high_distance_weight": 2.7,
        "short_hop_bonus": 1.2,
        "short_hop_range": 26,
        "ship_weight": 1.85,
        "high_ship_weight": 1.55,
        "overkill": 5,
        "high_prod_extra": 3,
        "enemy_extra": 9,
        "attack_fraction": 0.28,
        "max_attacks_per_turn": 1,
        "comet_bonus": 6,
    },
    "cw_probe_swarm": {
        "min_ships": 5,
        "min_reserve": 8,
        "reserve_prod_mult": 3.4,
        "panic_reserve_mult": 0.8,
        "neutral_bonus": -2,
        "neutral_tax": 22,
        "enemy_bonus": 48,
        "enemy_weak_bonus": 3.4,
        "counter_bonus": 8,
        "pressure_max": 84,
        "pressure_divisor": 9,
        "production_weight": 10,
        "high_production_weight": 18,
        "high_prod_tax": 30,
        "distance_weight": 1.65,
        "high_distance_weight": 1.45,
        "short_hop_bonus": 3.4,
        "short_hop_range": 50,
        "ship_weight": 0.7,
        "high_ship_weight": 0.65,
        "overkill": 1,
        "high_prod_extra": 0,
        "enemy_extra": 2,
        "attack_fraction": 0.74,
        "max_attacks_per_turn": 5,
        "comet_bonus": -4,
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
