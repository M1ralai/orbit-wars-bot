"""Sync: coordinated multi-source attack on target no single planet can take.
Guard: target prod >= 2, no single source can solo, total from nearby >= needed.
Runs AFTER core_attack so it only picks up targets nobody could handle alone.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.scoring import capture_cost
from bot.strategies.helpers import available_ships


def run_sync(my_planets, enemy_targets, doomed, threats,
             player, step, P, orbit_table, moves, assigned):
    for target in enemy_targets:
        if target["id"] in assigned:
            continue
        if target["production"] < 2:
            continue

        needed = capture_cost(target, player, assigned, P)
        if needed <= 0:
            continue

        candidates = []
        for src in my_planets:
            if src["id"] in doomed:
                continue
            if path_hits_sun(src["x"], src["y"], target["x"], target["y"]):
                continue
            avail = available_ships(src, threats, P)
            if avail <= 2:
                continue
            d = dist_xy(src["x"], src["y"], target["x"], target["y"])
            if d > 55:
                continue
            candidates.append((src, avail, d))

        if len(candidates) < 2:
            continue

        best_single = max(c[1] for c in candidates)
        if best_single >= needed:
            continue

        total = sum(c[1] for c in candidates)
        if total < needed:
            continue

        candidates.sort(key=lambda c: c[2])
        remaining = needed
        for src, avail, d in candidates:
            if remaining <= 0:
                break
            send = min(avail, remaining)
            angle = aim_angle(src, target, send, step, orbit_table)
            moves.append([src["id"], angle, send])
            assigned[target["id"]] = assigned.get(target["id"], 0) + send
            src["ships"] -= send
            remaining -= send
