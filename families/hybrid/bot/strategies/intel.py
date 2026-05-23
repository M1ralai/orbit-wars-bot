from bot.state import fleet_hit_eta


def fleet_hits_planet_eta(fleet, planet, step, orbit_table, max_steps=120, eta_cache=None):
    return fleet_hit_eta(fleet, planet, step, orbit_table, max_steps=max_steps, eta_cache=eta_cache)


def detect_counter_attack_targets(enemy_fleets, my_planets, step, orbit_table, eta_cache=None):
    counter_attack_targets = set()
    for fleet in enemy_fleets:
        if fleet["from_planet"] < 0:
            continue
        for planet in my_planets:
            if fleet_hits_planet_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache) is not None:
                counter_attack_targets.add(fleet["from_planet"])
                break
    return counter_attack_targets
