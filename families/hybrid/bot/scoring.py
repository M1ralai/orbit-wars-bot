from bot.geometry import path_hits_sun, dist_xy, predict_pos, travel_time


def capture_cost(target, player, assigned, P, travel_t=0.0):
    already = assigned.get(target["id"], 0)
    needed = int(target["ships"] + P["overkill"] - already)
    if target["owner"] not in (-1, player):
        needed += int(travel_t * target["production"] * P.get("production_forecast_mult", 1.0))
        needed += P["enemy_extra"]
    if target["production"] >= 3:
        needed += int(target["production"] * P["high_prod_extra"])
    return max(0, needed)


def score_target(src, target, player, step, assigned, P, comet_ids, orbit_table, threats, available, my_planets, counter_attack_targets):
    blocked = path_hits_sun(src["x"], src["y"], target["x"], target["y"])
    best_bridge = None
    if blocked:
        for p in my_planets:
            if p["id"] == src["id"]:
                continue
            if not path_hits_sun(src["x"], src["y"], p["x"], p["y"]) and not path_hits_sun(p["x"], p["y"], target["x"], target["y"]):
                if best_bridge is None or dist_xy(p["x"], p["y"], target["x"], target["y"]) < dist_xy(best_bridge["x"], best_bridge["y"], target["x"], target["y"]):
                    best_bridge = p
        if not best_bridge:
            return -1e9, None

    needed_static = capture_cost(target, player, assigned, P)
    if needed_static <= 0:
        return -1e8, None

    budget = max(1, int(available * P.get("attack_fraction", 0.85)))
    send = min(available, budget, needed_static)
    if send <= 0:
        return -1e8, None

    tx, ty = target["x"], target["y"]
    if blocked:
        d0 = dist_xy(src["x"], src["y"], best_bridge["x"], best_bridge["y"]) + dist_xy(best_bridge["x"], best_bridge["y"], tx, ty)
    else:
        d0 = dist_xy(src["x"], src["y"], tx, ty)
        
    tt = travel_time(d0, send)

    if target["id"] in orbit_table:
        pred = predict_pos(target["id"], step + tt, orbit_table)
        if pred:
            if blocked:
                if not path_hits_sun(best_bridge["x"], best_bridge["y"], pred[0], pred[1]):
                    tx, ty = pred
            else:
                if not path_hits_sun(src["x"], src["y"], pred[0], pred[1]):
                    tx, ty = pred

    if blocked:
        distance = dist_xy(src["x"], src["y"], best_bridge["x"], best_bridge["y"]) + dist_xy(best_bridge["x"], best_bridge["y"], tx, ty)
    else:
        distance = dist_xy(src["x"], src["y"], tx, ty)
        
    tt = travel_time(distance, send)
    needed = capture_cost(target, player, assigned, P, travel_t=tt)
    if needed <= 0:
        return -1e8, None

    high_prod = target["production"] >= 3
    is_enemy = target["owner"] not in (-1, player)
    is_neutral = target["owner"] == -1

    prod_w = P["high_production_weight"] if high_prod else P["production_weight"]
    dist_w = P["high_distance_weight"] if high_prod else P["distance_weight"]
    ship_w = P["high_ship_weight"] if high_prod else P["ship_weight"]

    if is_enemy:
        pressure = min(P["pressure_max"], step / P["pressure_divisor"]) if P["pressure_divisor"] > 0 else 0
        weak_bonus = max(0, 22 - target["ships"]) * P["enemy_weak_bonus"]
        owner_score = P["enemy_bonus"] + pressure + weak_bonus
    elif is_neutral:
        owner_score = P["neutral_bonus"] - P["neutral_tax"]
    else:
        owner_score = -1e8

    if threats.get(src["id"], 0):
        owner_score += P["counter_bonus"] if is_enemy else -P["counter_bonus"]

    local_bonus = max(0.0, P["short_hop_range"] - distance) * P["short_hop_bonus"]
    comet_bonus = P["comet_bonus"] if target["id"] in comet_ids else 0
    high_prod_tax = P["high_prod_tax"] if high_prod and is_neutral else 0
    counter_attack_bonus = P.get("counter_attack_bonus", 20.0) if target["id"] in counter_attack_targets else 0.0

    score = (
        target["production"] * prod_w
        + owner_score
        + local_bonus
        + comet_bonus
        + counter_attack_bonus
        - high_prod_tax
        - distance * dist_w
        - needed * ship_w
    )
    if blocked:
        score -= P.get("staging_penalty", 15.0)

    return score, (best_bridge["id"] if best_bridge else None)
