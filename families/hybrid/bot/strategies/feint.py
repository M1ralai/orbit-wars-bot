from bot.geometry import aim_angle, path_hits_sun
from bot.strategies.intel import fleet_hits_planet_eta


def run_feint(attack_targets, my_planets, my_fleets, late_game_behind, step, P, orbit_table, doomed_planets, moves, eta_cache=None):
    if not late_game_behind or (step % int(P.get("feint_interval", 6.0)) != 0):
        return

    enemy_fortresses = [p for p in attack_targets if p["owner"] != -1]
    enemy_fortresses.sort(key=lambda p: (-p["production"], -p["ships"]))

    feint_executed = False
    for target in enemy_fortresses:
        if feint_executed:
            break

        already_has_fleet = False
        for fleet in my_fleets:
            if fleet["ships"] < 1:
                continue
            if fleet_hits_planet_eta(fleet, target, step, orbit_table, eta_cache=eta_cache) is not None:
                already_has_fleet = True
                break

        if already_has_fleet:
            continue

        for src in my_planets:
            if src["id"] in doomed_planets:
                continue
            if src["ships"] < P["min_ships"] + int(P.get("feint_min_margin", 2.0)):
                continue

            if path_hits_sun(src["x"], src["y"], target["x"], target["y"]):
                continue

            angle = aim_angle(src, target, 1, step, orbit_table)
            moves.append([src["id"], angle, 1])
            src["ships"] -= 1
            feint_executed = True
            break
