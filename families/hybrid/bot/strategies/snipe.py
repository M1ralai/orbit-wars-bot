"""Snipe: steal a neutral right after enemy captures it.
Guard: step <= 120, enemy fleet heading to neutral, we can arrive ~1 step after capture.
"""
import math
from bot.geometry import dist_xy, path_hits_sun, predict_pos, travel_time
from bot.state import fleet_hit_eta
from bot.strategies.helpers import available_ships


def run_snipe(neutrals, enemy_fleets, my_planets, doomed, threats,
              step, P, orbit_table, moves, assigned):
    if step > 120:
        return

    eta_cache = {}
    for target in neutrals:
        if target["id"] in assigned:
            continue

        # Find enemy fleets heading to this neutral
        enemy_arrivals = []
        for f in enemy_fleets:
            eta = fleet_hit_eta(f, target, step, orbit_table, max_steps=60, eta_cache=eta_cache)
            if eta is not None:
                enemy_arrivals.append((f["ships"], step + eta))
        if not enemy_arrivals:
            continue

        # Simulate capture
        remaining = target["ships"]
        enemy_arrivals.sort(key=lambda x: x[1])
        capture_step, enemy_surviving = None, 0
        for ships, arr_step in enemy_arrivals:
            if ships > remaining:
                capture_step = arr_step
                enemy_surviving = ships - remaining
                break
            remaining -= ships
        if capture_step is None:
            continue

        our_eta = capture_step + 1 - step
        if our_eta <= 0:
            continue

        ships_to_beat = enemy_surviving + target["production"] + int(P["overkill"])
        pred = predict_pos(target["id"], capture_step + 1, orbit_table) if target["id"] in orbit_table else None
        tx = pred[0] if pred else target["x"]
        ty = pred[1] if pred else target["y"]

        for src in my_planets:
            if src["id"] in doomed:
                continue
            avail = available_ships(src, threats, P)
            if avail < ships_to_beat:
                continue
            if path_hits_sun(src["x"], src["y"], tx, ty):
                continue
            d = dist_xy(src["x"], src["y"], tx, ty)
            tt = travel_time(d, ships_to_beat)
            if abs(tt - our_eta) > 1.5:
                continue
            angle = math.atan2(ty - src["y"], tx - src["x"])
            moves.append([src["id"], angle, ships_to_beat])
            assigned[target["id"]] = assigned.get(target["id"], 0) + ships_to_beat
            src["ships"] -= ships_to_beat
            break
