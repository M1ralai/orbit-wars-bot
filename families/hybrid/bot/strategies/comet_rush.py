"""Comet Rush: prioritize capturing comet planets early for bonus production snowball.
Guard: comet planets exist + are neutral/enemy, early game.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.scoring import capture_cost
from bot.strategies.helpers import available_ships


def run_comet_rush(my_planets, targets, comet_ids, doomed, threats,
                   player, step, P, orbit_table, moves, assigned):
    if not comet_ids or step > 100:
        return

    comet_targets = [t for t in targets if t["id"] in comet_ids and t["id"] not in assigned]
    if not comet_targets:
        return

    # Sort by: neutrals first (easier), then by proximity
    comet_targets.sort(key=lambda t: (t["owner"] != -1, t["ships"]))

    for target in comet_targets[:2]:
        needed = capture_cost(target, player, assigned, P)
        if needed <= 0:
            continue

        # Find closest source
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
