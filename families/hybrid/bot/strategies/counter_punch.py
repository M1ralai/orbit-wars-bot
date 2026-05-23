"""Counter-Punch: enemy sent fleet away, their source planet is now weak — hit it.
Guard: enemy fleet in air, source planet exists + owner is enemy + ships dropped.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.scoring import capture_cost
from bot.strategies.helpers import available_ships


def run_counter_punch(my_planets, planets, enemy_fleets, doomed, threats,
                      player, step, P, orbit_table, moves, assigned):
    # Build map of enemy planets
    enemy_planets = {p["id"]: p for p in planets if p["owner"] not in (-1, player)}

    # Find enemy planets that just sent fleets (from_planet)
    weakened = {}
    for f in enemy_fleets:
        src_id = f["from_planet"]
        if src_id < 0 or src_id not in enemy_planets:
            continue
        weakened[src_id] = weakened.get(src_id, 0) + f["ships"]

    if not weakened:
        return

    # Sort by how weakened they are (most ships sent away first)
    targets = []
    for pid, ships_sent in weakened.items():
        ep = enemy_planets[pid]
        # Only counter if they sent a significant portion
        if ships_sent < ep["ships"] * 0.5 and ships_sent < 15:
            continue
        targets.append((ships_sent, ep))
    targets.sort(key=lambda x: -x[0])

    for ships_sent, target in targets[:3]:
        if target["id"] in assigned:
            continue
        needed = capture_cost(target, player, assigned, P)
        if needed <= 0:
            continue

        # Find closest planet that can take it
        for src in my_planets:
            if src["id"] in doomed:
                continue
            if path_hits_sun(src["x"], src["y"], target["x"], target["y"]):
                continue
            avail = available_ships(src, threats, P)
            if avail < needed:
                continue
            d = dist_xy(src["x"], src["y"], target["x"], target["y"])
            if d > 50:
                continue
            send = needed
            angle = aim_angle(src, target, send, step, orbit_table)
            moves.append([src["id"], angle, send])
            assigned[target["id"]] = assigned.get(target["id"], 0) + send
            src["ships"] -= send
            break
