"""Core Attack: the basic scoring loop — same as the simple bot.
Always active. Respects assigned dict from previous tactics.
"""
from bot.geometry import aim_angle
from bot.scoring import capture_cost, score_target
from bot.strategies.helpers import available_ships


def run_core_attack(my_planets, targets, doomed, threats,
                    player, step, P, comet_ids, orbit_table, moves, assigned):
    my_planets_sorted = sorted(my_planets, key=lambda p: p["ships"], reverse=True)

    for src in my_planets_sorted:
        if src["id"] in doomed:
            continue

        threat = threats.get(src["id"], 0)
        reserve = max(P["min_reserve"], int(src["production"] * P["reserve_prod_mult"])) + threat

        if src["ships"] < P["min_ships"] + threat:
            continue

        available = int(src["ships"] - reserve)
        if available <= 0:
            continue

        scored = []
        for t in targets:
            s = score_target(src, t, player, step, assigned, P, comet_ids, orbit_table)
            if s > -1e8:
                scored.append((s, t))

        if not scored:
            continue

        scored.sort(key=lambda x: x[0], reverse=True)

        for score_val, target in scored[:3]:
            if score_val < 0 or available <= 0:
                break

            needed = capture_cost(target, player, assigned, P)
            if needed <= 0:
                continue

            send = min(available, needed)
            remaining_def = target["ships"] - assigned.get(target["id"], 0)
            if send <= remaining_def:
                continue

            angle = aim_angle(src, target, send, step, orbit_table)
            moves.append([src["id"], angle, send])
            assigned[target["id"]] = assigned.get(target["id"], 0) + send
            available -= send
            src["ships"] -= send
