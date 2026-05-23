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
    "staging_penalty": {staging_penalty},
    "defense_worth_factor": {defense_worth_factor},
    "counter_attack_bonus": {counter_attack_bonus},
    "production_forecast_mult": {production_forecast_mult},
    "evac_eta_threshold": {evac_eta_threshold},
    "evac_minor_prod": {evac_minor_prod},
    "sync_max_eta": {sync_max_eta},
    "sync_min_target_prod": {sync_min_target_prod},
    "sync_min_target_ships": {sync_min_target_ships},
    "snipe_max_step": {snipe_max_step},
    "snipe_overkill": {snipe_overkill},
    "honeypot_min_prod": {honeypot_min_prod},
    "honeypot_reserve": {honeypot_reserve},
    "feint_interval": {feint_interval},
    "feint_min_margin": {feint_min_margin},
}


def generate_phase_configs(base):
    # Derive phases from the mutated base parameters
    early = dict(base)
    early["min_ships"] = max(2, base["min_ships"] - 3)
    early["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.4)
    early["neutral_bonus"] = base["neutral_bonus"] + 15
    early["neutral_tax"] = max(0, base.get("neutral_tax", 0) - 8)
    early["pressure_max"] = max(0, base.get("pressure_max", 0) - 16)
    early["attack_fraction"] = min(0.98, base.get("attack_fraction", 0.85) + 0.08)
    early["comet_bonus"] = base.get("comet_bonus", 10) + 5

    mid = dict(base)
    mid["enemy_bonus"] = base["enemy_bonus"] + 10
    mid["pressure_max"] = base.get("pressure_max", 0) + 4

    late = dict(base)
    late["min_ships"] = max(2, base["min_ships"] - 2)
    late["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.6)
    late["neutral_bonus"] = max(0, base["neutral_bonus"] - 3)
    late["neutral_tax"] = base.get("neutral_tax", 0) + 8
    late["enemy_bonus"] = base["enemy_bonus"] + 20
    late["pressure_max"] = base.get("pressure_max", 0) + 12
    late["counter_bonus"] = base.get("counter_bonus", 0) + 8
    late["attack_fraction"] = min(0.98, base.get("attack_fraction", 0.85) + 0.12)
    late["comet_bonus"] = max(0, base.get("comet_bonus", 10) - 5)

    return {"early": early, "mid": mid, "late": late}


PARAMS_CONFIG = generate_phase_configs(BASE_PARAMS)
