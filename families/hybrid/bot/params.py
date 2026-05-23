# Hybrid bot params - same core as simple bot + production_forecast_mult
BASE_PARAMS = {
    "min_ships": {min_ships},
    "min_reserve": {min_reserve},
    "reserve_prod_mult": {reserve_prod_mult},
    "neutral_bonus": {neutral_bonus},
    "enemy_bonus": {enemy_bonus},
    "pressure_max": {pressure_max},
    "pressure_divisor": {pressure_divisor},
    "production_weight": {production_weight},
    "high_production_weight": {high_production_weight},
    "distance_weight": {distance_weight},
    "high_distance_weight": {high_distance_weight},
    "ship_weight": {ship_weight},
    "high_ship_weight": {high_ship_weight},
    "overkill": {overkill},
    "high_prod_extra": {high_prod_extra},
    "enemy_extra": {enemy_extra},
    "comet_bonus": {comet_bonus},
    "production_forecast_mult": {production_forecast_mult},
}


def generate_phase_configs(base):
    early = dict(base)
    early["min_ships"] = max(2, base["min_ships"] - 3)
    early["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.4)
    early["neutral_bonus"] = base["neutral_bonus"] + 15
    early["pressure_max"] = 0
    early["comet_bonus"] = base.get("comet_bonus", 10) + 5

    mid = dict(base)
    mid["enemy_bonus"] = base["enemy_bonus"] + 10
    mid["pressure_max"] = base.get("pressure_max", 0) + 4

    late = dict(base)
    late["min_ships"] = max(2, base["min_ships"] - 2)
    late["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.6)
    late["neutral_bonus"] = max(0, base["neutral_bonus"] - 3)
    late["enemy_bonus"] = base["enemy_bonus"] + 20
    late["pressure_max"] = base.get("pressure_max", 0) + 12
    late["comet_bonus"] = max(0, base.get("comet_bonus", 10) - 5)

    return {"early": early, "mid": mid, "late": late}


PARAMS_CONFIG = generate_phase_configs(BASE_PARAMS)
