"""Chain Expand: grab nearest neutrals in a chain, using newly captured planets as staging.
Guard: neutrals exist, early/mid game. Prioritize closest neutrals to existing planets.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.scoring import capture_cost
from bot.strategies.helpers import available_ships


def run_chain_expand(my_planets, neutrals, doomed, threats,
                     player, step, P, orbit_table, moves, assigned):
    if not neutrals:
        return

    # Score neutrals by closeness to any of our planets
    scored = []
    for target in neutrals:
        if target["id"] in assigned:
            continue
        best_d = 999
        best_src = None
        for src in my_planets:
            if src["id"] in doomed:
                continue
            if path_hits_sun(src["x"], src["y"], target["x"], target["y"]):
                continue
            d = dist_xy(src["x"], src["y"], target["x"], target["y"])
            if d < best_d:
                best_d = d
                best_src = src
        if best_src is None:
            continue
        # Prioritize: close + high production + few ships
        score = target["production"] * 8 - best_d * 0.8 - target["ships"] * 0.5
        scored.append((score, target, best_src, best_d))

    scored.sort(key=lambda x: -x[0])

    for score, target, best_src, d in scored[:4]:
        needed = capture_cost(target, player, assigned, P)
        if needed <= 0:
            continue
        avail = available_ships(best_src, threats, P)
        if avail < needed:
            continue
        send = needed
        angle = aim_angle(best_src, target, send, step, orbit_table)
        moves.append([best_src["id"], angle, send])
        assigned[target["id"]] = assigned.get(target["id"], 0) + send
        best_src["ships"] -= send
