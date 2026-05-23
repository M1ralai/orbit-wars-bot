from bot.geometry import aim_angle, dist_xy, path_hits_sun, predict_pos, travel_time
from bot.scoring import capture_cost, score_target
from bot.strategies.defense import reinforce_targets, reserve_for
from bot.strategies.intel import fleet_hits_planet_eta


def run_pressure_plan(
    my_planets,
    attack_targets,
    my_fleets,
    player,
    step,
    P,
    orbit_table,
    comet_ids,
    net_threats,
    doomed_planets,
    late_game_ahead,
    honeypot_id,
    counter_attack_targets,
    moves,
    assigned,
    eta_cache=None,
):
    my_planets.sort(
        key=lambda p: (
            net_threats.get(p["id"], 0) <= 0,
            p["ships"],
            p["production"],
        ),
        reverse=True,
    )

    attacks = 0
    threatened_homes = reinforce_targets(my_planets, net_threats, P)
    for src in my_planets:
        is_doomed = src["id"] in doomed_planets
        threat = 0 if is_doomed else net_threats.get(src["id"], 0)
        if not is_doomed and late_game_ahead and src["id"] == honeypot_id and threat == 0:
            reserve = min(int(P.get("honeypot_reserve", 4.0)), src["ships"])
        else:
            reserve = 0 if is_doomed else reserve_for(src, threat, P)

        if not is_doomed and src["ships"] < P["min_ships"] + threat:
            continue

        available = int(src["ships"] - reserve)
        if available <= 0:
            continue

        for home in threatened_homes[:2]:
            if home["id"] == src["id"] or path_hits_sun(src["x"], src["y"], home["x"], home["y"]):
                continue
            if dist_xy(src["x"], src["y"], home["x"], home["y"]) > P["short_hop_range"] * 1.7:
                continue
            send = min(available // 2, max(4, int(net_threats.get(home["id"], 0) * 0.7)))
            if is_doomed:
                send = available
            if send <= 0:
                continue
            moves.append([src["id"], aim_angle(src, home, send, step, orbit_table), send])
            available -= send
            net_threats[home["id"]] = max(0, net_threats.get(home["id"], 0) - send)
            break

        if attacks >= P["max_attacks_per_turn"] or available <= 0:
            continue

        scored = []
        for target in attack_targets:
            score, bridge_id = score_target(src, target, player, step, assigned, P, comet_ids, orbit_table, net_threats, available, my_planets, counter_attack_targets)
            if score > -1e8:
                scored.append((score, target, bridge_id))

        scored.sort(key=lambda item: item[0], reverse=True)
        for score, target, bridge_id in scored[:3]:
            if score < 0 or attacks >= P["max_attacks_per_turn"] or available <= 0:
                break

            tx, ty = target["x"], target["y"]
            aim_target = target
            is_staging = False
            if bridge_id is not None:
                bridge_planet = next((p for p in my_planets if p["id"] == bridge_id), None)
                if bridge_planet:
                    aim_target = bridge_planet
                    is_staging = True
                    tx, ty = bridge_planet["x"], bridge_planet["y"]

            if aim_target["id"] in orbit_table:
                d0 = dist_xy(src["x"], src["y"], tx, ty)
                rough_send = max(1, min(available, target["ships"] + P["overkill"]))
                tt = travel_time(d0, rough_send)
                pred = predict_pos(aim_target["id"], step + tt, orbit_table)
                if pred and not path_hits_sun(src["x"], src["y"], pred[0], pred[1]):
                    tx, ty = pred

            distance = dist_xy(src["x"], src["y"], tx, ty)
            rough_send = max(1, min(available, target["ships"] + P["overkill"]))
            tt = travel_time(distance, rough_send)

            incoming_friendly_etas = []
            for fleet in my_fleets:
                if fleet["ships"] < 4:
                    continue
                eta = fleet_hits_planet_eta(fleet, target, step, orbit_table, eta_cache=eta_cache)
                if eta is not None:
                    incoming_friendly_etas.append(eta)

            target_max_eta = max(incoming_friendly_etas) if incoming_friendly_etas else 0.0

            is_major = target["ships"] >= P.get("sync_min_target_ships", 35.0) or target["production"] >= P.get("sync_min_target_prod", 3.0)
            if not is_doomed and is_major and 0.0 < target_max_eta <= P.get("sync_max_eta", 10.0) and tt < target_max_eta - 1.0:
                continue

            needed = capture_cost(target, player, assigned, P, travel_t=tt)

            budget = max(1, int(available * (1.0 if is_doomed else P["attack_fraction"])))
            send = min(available, budget, needed)
            if is_doomed:
                send = available
            if send <= 0:
                continue

            moves.append([src["id"], aim_angle(src, aim_target, send, step, orbit_table), send])
            if not is_staging:
                assigned[target["id"]] = assigned.get(target["id"], 0) + send
            available -= send
            attacks += 1
