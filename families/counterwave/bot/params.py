# Counterwave is intentionally not an eco-first family. It keeps a thicker
# reserve, taxes neutral expansion, and looks for short enemy/counter punches.
BASE_PARAMS = {
    "min_ships": {min_ships},
    "min_reserve": {min_reserve},
    "reserve_prod_mult": {reserve_prod_mult},
    "panic_reserve_mult": {panic_reserve_mult},
    "neutral_bonus": {neutral_bonus},
    "neutral_tax": {neutral_tax},
    "enemy_bonus": {enemy_bonus},
    "enemy_weak_bonus": {enemy_weak_bonus},
    "counter_bonus": {counter_bonus},
    "pressure_max": {pressure_max},
    "pressure_divisor": {pressure_divisor},
    "production_weight": {production_weight},
    "high_production_weight": {high_production_weight},
    "high_prod_tax": {high_prod_tax},
    "distance_weight": {distance_weight},
    "high_distance_weight": {high_distance_weight},
    "short_hop_bonus": {short_hop_bonus},
    "short_hop_range": {short_hop_range},
    "ship_weight": {ship_weight},
    "high_ship_weight": {high_ship_weight},
    "overkill": {overkill},
    "high_prod_extra": {high_prod_extra},
    "enemy_extra": {enemy_extra},
    "attack_fraction": {attack_fraction},
    "max_attacks_per_turn": {max_attacks_per_turn},
    "comet_bonus": {comet_bonus},
}


def generate_phase_configs(base):
    early = dict(base)
    early["enemy_bonus"] = max(0, base["enemy_bonus"] - 8)
    early["neutral_bonus"] = base["neutral_bonus"] + 5
    early["neutral_tax"] = max(0, base["neutral_tax"] - 5)
    early["pressure_max"] = max(0, base["pressure_max"] - 16)
    early["attack_fraction"] = min(0.72, base["attack_fraction"] + 0.08)
    early["comet_bonus"] = base["comet_bonus"] + 4

    mid = dict(base)

    late = dict(base)
    late["enemy_bonus"] = base["enemy_bonus"] + 14
    late["neutral_tax"] = base["neutral_tax"] + 8
    late["pressure_max"] = base["pressure_max"] + 18
    late["counter_bonus"] = base["counter_bonus"] + 8
    late["attack_fraction"] = min(0.82, base["attack_fraction"] + 0.12)

    return {"early": early, "mid": mid, "late": late}


PARAMS_CONFIG = generate_phase_configs(BASE_PARAMS)
