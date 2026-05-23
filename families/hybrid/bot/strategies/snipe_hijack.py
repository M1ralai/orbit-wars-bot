import math

from bot.geometry import dist_xy, path_hits_sun, predict_pos, travel_time
from bot.strategies.defense import reserve_for
from bot.strategies.intel import fleet_hits_planet_eta


def first_enemy_capture(target_enemy_fleets, neutral_ships):
    remaining_neutral = neutral_ships
    for ships, arrival_step in sorted(target_enemy_fleets, key=lambda x: x[1]):
        if ships > remaining_neutral:
            return ships - remaining_neutral, arrival_step
        remaining_neutral = max(0, remaining_neutral - ships)
    return None, None


def send_range_arriving_at(src, pred, available, eta_target):
    max_send = int(available)
    d0 = dist_xy(src["x"], src["y"], pred[0], pred[1])
    min_exact = None
    max_exact = None
    for send in range(max_send, 0, -1):
        eta = int(0.5 + travel_time(d0, send))
        if eta == eta_target:
            if max_exact is None:
                max_exact = send
            min_exact = send
        elif max_exact is not None and eta > eta_target:
            break
    return min_exact, max_exact


def run_snipe_hijack(
    attack_targets,
    enemy_fleets,
    my_planets,
    step,
    P,
    orbit_table,
    doomed_planets,
    net_threats,
    moves,
    assigned,
    eta_cache=None,
):
    if step >= P.get("snipe_max_step", 90.0):
        return

    for target in attack_targets:
        if target["owner"] != -1:
            continue

        target_enemy_fleets = []
        for fleet in enemy_fleets:
            eta = fleet_hits_planet_eta(fleet, target, step, orbit_table, max_steps=60, eta_cache=eta_cache)
            if eta is not None:
                target_enemy_fleets.append((fleet["ships"], step + eta))

        if not target_enemy_fleets:
            continue

        enemy_surviving, K = first_enemy_capture(target_enemy_fleets, target["ships"])
        if enemy_surviving is None:
            continue

        A_target = K + 1
        eta_target = A_target - step
        if eta_target <= 0:
            continue

        pred = predict_pos(target["id"], A_target, orbit_table) if target["id"] in orbit_table else (target["x"], target["y"])
        enemy_total = enemy_surviving + target["production"]
        S_needed = int(enemy_total + P.get("snipe_overkill", 3.0))

        valid_snipers = []
        for src in my_planets:
            if src["id"] in doomed_planets:
                continue

            threat = net_threats.get(src["id"], 0)
            reserve = reserve_for(src, threat, P)
            available = int(src["ships"] - reserve)
            if available <= 0:
                continue

            if path_hits_sun(src["x"], src["y"], pred[0], pred[1]):
                continue

            min_send, max_send = send_range_arriving_at(src, pred, available, eta_target)
            if min_send and max_send:
                valid_snipers.append((src, min_send, max_send))

        total_exact = sum(max_send for _, _, max_send in valid_snipers)
        if total_exact < S_needed:
            continue

        valid_snipers.sort(key=lambda item: (item[1], item[2]))
        remaining_needed = S_needed
        for src, min_send, max_send in valid_snipers:
            if remaining_needed <= 0:
                break
            if remaining_needed < min_send:
                send = min_send
            else:
                send = min(max_send, remaining_needed)
            angle = math.atan2(pred[1] - src["y"], pred[0] - src["x"])
            moves.append([src["id"], angle, send])
            assigned[target["id"]] = assigned.get(target["id"], 0) + send
            remaining_needed -= send
            src["ships"] -= send
