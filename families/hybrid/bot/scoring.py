from bot.geometry import path_hits_sun, dist_xy, predict_pos, travel_time


def capture_cost(target, player, assigned, P):
    already = assigned.get(target["id"], 0)
    needed = int(target["ships"] + P["overkill"] - already)
    if target["production"] >= 3:
        needed += int(target["production"] * P["high_prod_extra"])
    if target["owner"] not in (-1, player):
        needed += P["enemy_extra"]
        # Production forecast: enemy produces while fleet travels
        d_approx = 30.0  # rough average distance
        tt_approx = travel_time(d_approx, max(1, needed))
        needed += int(tt_approx * target["production"] * P.get("production_forecast_mult", 0.5))
    return max(0, needed)


def score_target(src, target, player, step, assigned, P, comet_ids, orbit_table):
    if path_hits_sun(src["x"], src["y"], target["x"], target["y"]):
        return -1e9

    needed = capture_cost(target, player, assigned, P)
    if needed <= 0:
        return -1e8

    tx, ty = target["x"], target["y"]
    if target["id"] in orbit_table:
        d0 = dist_xy(src["x"], src["y"], tx, ty)
        pred = predict_pos(target["id"], step + travel_time(d0, 20), orbit_table)
        if pred and not path_hits_sun(src["x"], src["y"], pred[0], pred[1]):
            tx, ty = pred

    distance = dist_xy(src["x"], src["y"], tx, ty)
    high_prod = target["production"] >= 3
    is_enemy = target["owner"] not in (-1, player)

    owner_bonus = P["neutral_bonus"] if target["owner"] == -1 else P["enemy_bonus"]
    pressure = min(P["pressure_max"], step / P["pressure_divisor"]) if is_enemy and P["pressure_divisor"] > 0 else 0
    prod_w = P["high_production_weight"] if high_prod else P["production_weight"]
    dist_w = P["high_distance_weight"] if high_prod else P["distance_weight"]
    ship_w = P["high_ship_weight"] if high_prod else P["ship_weight"]

    comet_bonus = P["comet_bonus"] if target["id"] in comet_ids else 0

    return (
        target["production"] * prod_w
        + owner_bonus
        + pressure
        + comet_bonus
        - distance * dist_w
        - needed * ship_w
    )
