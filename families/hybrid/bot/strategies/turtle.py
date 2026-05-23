"""Turtle: when behind or under siege, pull ships from low-value planets to high-value ones.
Guard: BEHIND_DESPERATE or UNDER_SIEGE stance. Only consolidate, don't attack.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.strategies.helpers import available_ships


def run_turtle(my_planets, doomed, threats, step, P, orbit_table, moves):
    if len(my_planets) < 2:
        return

    # Find our fortress: highest production planet
    fortress = max(my_planets, key=lambda p: (p["production"], p["ships"]))

    # Pull ships from low-prod planets to fortress
    for src in my_planets:
        if src["id"] == fortress["id"] or src["id"] in doomed:
            continue
        if src["production"] >= fortress["production"]:
            continue  # don't drain equally good planets
        if path_hits_sun(src["x"], src["y"], fortress["x"], fortress["y"]):
            continue
        d = dist_xy(src["x"], src["y"], fortress["x"], fortress["y"])
        if d > 45:
            continue

        avail = available_ships(src, threats, P)
        # In turtle mode, send more aggressively — keep only min_reserve
        send = max(0, src["ships"] - P["min_reserve"] - threats.get(src["id"], 0))
        if send <= 2:
            continue

        angle = aim_angle(src, fortress, send, step, orbit_table)
        moves.append([src["id"], angle, send])
        src["ships"] -= send
