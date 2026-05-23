"""Production Starve: target enemy's highest production planet to cut their economy.
Guard: FRONTLINE or AHEAD, enemy has prod >= 3 planet, we have enough ships nearby.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.scoring import capture_cost
from bot.strategies.helpers import available_ships


def run_prod_starve(my_planets, enemy_targets, doomed, threats,
                    player, step, P, orbit_table, moves, assigned):
    # Find enemy's best production planets
    high_prod = [t for t in enemy_targets if t["production"] >= 3 and t["id"] not in assigned]
    if not high_prod:
        return

    high_prod.sort(key=lambda t: (-t["production"], t["ships"]))

    for target in high_prod[:2]:
        needed = capture_cost(target, player, assigned, P)
        if needed <= 0:
            continue

        # Find best source: closest with enough ships
        best_src, best_d = None, 999
        for src in my_planets:
            if src["id"] in doomed:
                continue
            if path_hits_sun(src["x"], src["y"], target["x"], target["y"]):
                continue
            avail = available_ships(src, threats, P)
            if avail < needed:
                continue
            d = dist_xy(src["x"], src["y"], target["x"], target["y"])
            if d < best_d:
                best_d = d
                best_src = src

        if best_src is None:
            continue

        send = needed
        angle = aim_angle(best_src, target, send, step, orbit_table)
        moves.append([best_src["id"], angle, send])
        assigned[target["id"]] = assigned.get(target["id"], 0) + send
        best_src["ships"] -= send
