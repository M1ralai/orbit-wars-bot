"""Vulture: attack enemy planets that just got weakened (low ships relative to production).
Guard: enemy planet ships < production * 4, meaning it recently lost a battle or sent troops.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.scoring import capture_cost
from bot.strategies.helpers import available_ships


def run_vulture(my_planets, enemy_targets, doomed, threats,
                player, step, P, orbit_table, moves, assigned):
    # Find weak enemy planets (ships much lower than expected)
    weak = []
    for t in enemy_targets:
        if t["id"] in assigned:
            continue
        if t["ships"] < t["production"] * 4 and t["production"] >= 1:
            weak.append(t)

    if not weak:
        return

    weak.sort(key=lambda t: t["ships"])  # easiest first

    for target in weak[:3]:
        needed = capture_cost(target, player, assigned, P)
        if needed <= 0:
            continue

        # Find closest source that can take it
        for src in sorted(my_planets, key=lambda s: dist_xy(s["x"], s["y"], target["x"], target["y"])):
            if src["id"] in doomed:
                continue
            if path_hits_sun(src["x"], src["y"], target["x"], target["y"]):
                continue
            avail = available_ships(src, threats, P)
            if avail < needed:
                continue
            send = needed
            angle = aim_angle(src, target, send, step, orbit_table)
            moves.append([src["id"], angle, send])
            assigned[target["id"]] = assigned.get(target["id"], 0) + send
            src["ships"] -= send
            break
