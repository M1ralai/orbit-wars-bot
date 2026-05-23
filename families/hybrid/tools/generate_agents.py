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
    "evac_minor_prod",
    "sync_min_target_prod",
    "sync_min_target_ships",
    "snipe_max_step",
    "snipe_overkill",
    "honeypot_min_prod",
    "honeypot_reserve",
    "feint_interval",
    "feint_min_margin",
}

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


def build_template():
    bot_dir = Path(__file__).resolve().parent.parent / "bot"
    order = [
        "params.py",
        "geometry.py",
        "state.py",
        "scoring.py",
        "strategies/defense.py",
        "strategies/intel.py",
        "strategies/snipe_hijack.py",
        "strategies/honeypot.py",
        "strategies/feint.py",
        "strategies/pressure.py",
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
    "hybrid_v009_dna": {
        "min_ships": 18,
        "min_reserve": 2,
        "reserve_prod_mult": 1.8,
        "panic_reserve_mult": 0.0,
        "neutral_bonus": 28,
        "neutral_tax": 0,
        "enemy_bonus": 26,
        "enemy_weak_bonus": 0.0,
        "counter_bonus": 0,
        "pressure_max": 0,
        "pressure_divisor": 49,
        "production_weight": 44,
        "high_production_weight": 57,
        "high_prod_tax": 0,
        "distance_weight": 2.2162,
        "high_distance_weight": 2.1939,
        "short_hop_bonus": 0.0,
        "short_hop_range": 16,
        "ship_weight": 1.1722,
        "high_ship_weight": 0.8948,
        "overkill": 3,
        "high_prod_extra": 3,
        "enemy_extra": 8,
        "attack_fraction": 0.95,
        "max_attacks_per_turn": 8,
        "comet_bonus": 10,
        "staging_penalty": 15.0,
        "defense_worth_factor": 10.0,
        "counter_attack_bonus": 20.0,
    },
    "hybrid_cw014_dna": {
        "min_ships": 16,
        "min_reserve": 6,
        "reserve_prod_mult": 3.0,
        "panic_reserve_mult": 0.6529,
        "neutral_bonus": 1,
        "neutral_tax": 13,
        "enemy_bonus": 44,
        "enemy_weak_bonus": 0.0,
        "counter_bonus": 0,
        "pressure_max": 31,
        "pressure_divisor": 24,
        "production_weight": 18,
        "high_production_weight": 44,
        "high_prod_tax": 17,
        "distance_weight": 2.7814,
        "high_distance_weight": 2.7814,
        "short_hop_bonus": 0.0,
        "short_hop_range": 16,
        "ship_weight": 0.9165,
        "high_ship_weight": 0.7812,
        "overkill": 8,
        "high_prod_extra": 0,
        "enemy_extra": 14,
        "attack_fraction": 0.82,
        "max_attacks_per_turn": 1,
        "comet_bonus": 14,
        "staging_penalty": 15.0,
        "defense_worth_factor": 10.0,
        "counter_attack_bonus": 20.0,
    },
    "hybrid_aggressive_defense": {
        "min_ships": 14,
        "min_reserve": 4,
        "reserve_prod_mult": 2.2,
        "panic_reserve_mult": 0.8,
        "neutral_bonus": 24,
        "neutral_tax": 2,
        "enemy_bonus": 34,
        "enemy_weak_bonus": 0.5,
        "counter_bonus": 12,
        "pressure_max": 10,
        "pressure_divisor": 30,
        "production_weight": 36,
        "high_production_weight": 50,
        "high_prod_tax": 4,
        "distance_weight": 2.3,
        "high_distance_weight": 2.0,
        "short_hop_bonus": 1.2,
        "short_hop_range": 24,
        "ship_weight": 1.05,
        "high_ship_weight": 0.85,
        "overkill": 3,
        "high_prod_extra": 2,
        "enemy_extra": 10,
        "attack_fraction": 0.90,
        "max_attacks_per_turn": 5,
        "comet_bonus": 12,
        "staging_penalty": 15.0,
        "defense_worth_factor": 10.0,
        "counter_attack_bonus": 20.0,
    },
    "hybrid_tempo_expand": {
        "min_ships": 12,
        "min_reserve": 3,
        "reserve_prod_mult": 2.0,
        "panic_reserve_mult": 0.5,
        "neutral_bonus": 26,
        "neutral_tax": 0,
        "enemy_bonus": 28,
        "enemy_weak_bonus": 0.0,
        "counter_bonus": 6,
        "pressure_max": 8,
        "pressure_divisor": 40,
        "production_weight": 40,
        "high_production_weight": 52,
        "high_prod_tax": 0,
        "distance_weight": 2.2,
        "high_distance_weight": 1.9,
        "short_hop_bonus": 0.5,
        "short_hop_range": 20,
        "ship_weight": 1.1,
        "high_ship_weight": 0.9,
        "overkill": 3,
        "high_prod_extra": 2,
        "enemy_extra": 8,
        "attack_fraction": 0.95,
        "max_attacks_per_turn": 6,
        "comet_bonus": 11,
        "staging_penalty": 15.0,
        "defense_worth_factor": 10.0,
        "counter_attack_bonus": 20.0,
    },
    "hybrid_smart_defense": {
        "min_ships": 15,
        "min_reserve": 5,
        "reserve_prod_mult": 2.6,
        "panic_reserve_mult": 1.0,
        "neutral_bonus": 16,
        "neutral_tax": 6,
        "enemy_bonus": 38,
        "enemy_weak_bonus": 1.0,
        "counter_bonus": 20,
        "pressure_max": 20,
        "pressure_divisor": 28,
        "production_weight": 28,
        "high_production_weight": 46,
        "high_prod_tax": 8,
        "distance_weight": 2.5,
        "high_distance_weight": 2.2,
        "short_hop_bonus": 1.8,
        "short_hop_range": 30,
        "ship_weight": 1.2,
        "high_ship_weight": 1.0,
        "overkill": 4,
        "high_prod_extra": 1,
        "enemy_extra": 12,
        "attack_fraction": 0.85,
        "max_attacks_per_turn": 4,
        "comet_bonus": 13,
        "staging_penalty": 15.0,
        "defense_worth_factor": 10.0,
        "counter_attack_bonus": 20.0,
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

    defaults = {
        "production_forecast_mult": 1.0,
        "evac_eta_threshold": 3.0,
        "evac_minor_prod": 2,
        "sync_max_eta": 10.0,
        "sync_min_target_prod": 3,
        "sync_min_target_ships": 35,
        "snipe_max_step": 90,
        "snipe_overkill": 3,
        "honeypot_min_prod": 3,
        "honeypot_reserve": 4,
        "feint_interval": 6,
        "feint_min_margin": 2,
    }
    for name, params in CANDIDATES.items():
        for k, v in defaults.items():
            if k not in params:
                params[k] = v

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
