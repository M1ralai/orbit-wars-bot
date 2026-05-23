from bot.geometry import aim_angle, dist_xy, path_hits_sun, predict_pos, travel_time
from bot.strategies.defense import reserve_for


def choose_honeypot(my_planets, late_game_ahead, P):
    if not late_game_ahead:
        return None

    min_prod = int(P.get("honeypot_min_prod", 3.0))
    candidates = [p for p in my_planets if p["production"] >= min_prod]
    if not candidates:
        candidates = [p for p in my_planets if p["production"] >= max(1, min_prod - 1)]
    if not candidates:
        return None

    candidates.sort(key=lambda p: (-p["production"], p["id"]))
    return candidates[0]["id"]


def run_honeypot_trap(
    my_planets,
    threats_det,
    net_threats,
    late_game_ahead,
    honeypot_id,
    step,
    P,
    orbit_table,
    doomed_planets,
    moves,
):
    if not late_game_ahead or honeypot_id is None or not threats_det.get(honeypot_id, []):
        return

    p_threats = list(threats_det[honeypot_id])
    p_threats.sort(key=lambda x: x[1])
    enemy_ships, enemy_eta = p_threats[0]
    enemy_eta = max(1, int(0.5 + enemy_eta))

    hp_planet = next((p for p in my_planets if p["id"] == honeypot_id), None)
    if not hp_planet:
        return

    hp_ships_at_arrival = hp_planet["ships"] + int(enemy_eta * hp_planet["production"])
    deficit = enemy_ships - hp_ships_at_arrival
    if deficit <= 0:
        return

    needed_reinf = deficit + P.get("snipe_overkill", 3.0)
    for neighbor in my_planets:
        if neighbor["id"] == honeypot_id or neighbor["id"] in doomed_planets:
            continue

        neigh_threat = net_threats.get(neighbor["id"], 0)
        neigh_res = reserve_for(neighbor, neigh_threat, P)
        neigh_avail = int(neighbor["ships"] - neigh_res)
        if neigh_avail <= 0:
            continue

        send = min(neigh_avail, needed_reinf)
        d0 = dist_xy(neighbor["x"], neighbor["y"], hp_planet["x"], hp_planet["y"])
        tt = travel_time(d0, send)
        eta = int(0.5 + tt)
        target_step = step + eta
        pred_hp = predict_pos(honeypot_id, target_step, orbit_table) if honeypot_id in orbit_table else (hp_planet["x"], hp_planet["y"])

        if eta <= enemy_eta and not path_hits_sun(neighbor["x"], neighbor["y"], pred_hp[0], pred_hp[1]):
            moves.append([neighbor["id"], aim_angle(neighbor, hp_planet, send, step, orbit_table), send])
            needed_reinf -= send
            neighbor["ships"] -= send
            net_threats[honeypot_id] = max(0, net_threats.get(honeypot_id, 0) - send)
            if needed_reinf <= 0:
                break
