"""Overflow Push: when a planet accumulates too many ships, push excess to nearest target.
Guard: planet ships > production * 15, prevents idle ship accumulation.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.scoring import capture_cost
from bot.strategies.helpers import available_ships


def run_overflow(my_planets, targets, doomed, threats,
                 player, step, P, orbit_table, moves, assigned):
    for src in my_planets:
        if src["id"] in doomed:
            continue
        # Only trigger when ships are way above normal
        threshold = max(30, src["production"] * 15)
        if src["ships"] < threshold:
            continue

        avail = available_ships(src, threats, P)
        if avail <= 5:
            continue

        # Find closest target we can attack
        best_target, best_d = None, 999
        for t in targets:
            if path_hits_sun(src["x"], src["y"], t["x"], t["y"]):
                continue
            d = dist_xy(src["x"], src["y"], t["x"], t["y"])
            if d < best_d:
                best_d = d
                best_target = t

        if best_target is None:
            continue

        needed = capture_cost(best_target, player, assigned, P)
        if needed <= 0:
            continue

        send = min(avail, needed)
        remaining_def = best_target["ships"] - assigned.get(best_target["id"], 0)
        if send <= remaining_def:
            continue

        angle = aim_angle(src, best_target, send, step, orbit_table)
        moves.append([src["id"], angle, send])
        assigned[best_target["id"]] = assigned.get(best_target["id"], 0) + send
        src["ships"] -= send
