import math
# Counterwave is intentionally not an eco-first family. It keeps a thicker
# reserve, taxes neutral expansion, and looks for short enemy/counter punches.
BASE_PARAMS = {
    "min_ships": 20,
    "min_reserve": 2,
    "reserve_prod_mult": 1.5,
    "panic_reserve_mult": 0.8252,
    "neutral_bonus": 25,
    "neutral_tax": 24,
    "enemy_bonus": 24,
    "enemy_weak_bonus": 0.8095,
    "counter_bonus": 19,
    "pressure_max": 19,
    "pressure_divisor": 70,
    "production_weight": 42,
    "high_production_weight": 46,
    "high_prod_tax": 1,
    "distance_weight": 2.3661,
    "high_distance_weight": 1.8908,
    "short_hop_bonus": 0.2397,
    "short_hop_range": 16,
    "ship_weight": 1.1942,
    "high_ship_weight": 1.1942,
    "overkill": 5,
    "high_prod_extra": 5,
    "enemy_extra": 6,
    "attack_fraction": 0.9282,
    "max_attacks_per_turn": 2,
    "comet_bonus": 14,
    "staging_penalty": 14.8587,
    "defense_worth_factor": 12.2035,
    "counter_attack_bonus": 36.9549,
    "production_forecast_mult": 1.0616,
    "evac_eta_threshold": 3.0835,
    "evac_minor_prod": 3,
    "sync_max_eta": 8.7991,
    "sync_min_target_prod": 1,
    "sync_min_target_ships": 31,
    "snipe_max_step": 86,
    "snipe_overkill": 1,
    "honeypot_min_prod": 5,
    "honeypot_reserve": 9,
    "feint_interval": 6,
    "feint_min_margin": 1,
}


def generate_phase_configs(base):
    # Derive phases from the mutated base parameters
    early = dict(base)
    early["min_ships"] = max(2, base["min_ships"] - 3)
    early["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.4)
    early["neutral_bonus"] = base["neutral_bonus"] + 15
    early["neutral_tax"] = max(0, base.get("neutral_tax", 0) - 8)
    early["pressure_max"] = max(0, base.get("pressure_max", 0) - 16)
    early["attack_fraction"] = min(0.98, base.get("attack_fraction", 0.85) + 0.08)
    early["comet_bonus"] = base.get("comet_bonus", 10) + 5

    mid = dict(base)
    mid["enemy_bonus"] = base["enemy_bonus"] + 10
    mid["pressure_max"] = base.get("pressure_max", 0) + 4

    late = dict(base)
    late["min_ships"] = max(2, base["min_ships"] - 2)
    late["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.6)
    late["neutral_bonus"] = max(0, base["neutral_bonus"] - 3)
    late["neutral_tax"] = base.get("neutral_tax", 0) + 8
    late["enemy_bonus"] = base["enemy_bonus"] + 20
    late["pressure_max"] = base.get("pressure_max", 0) + 12
    late["counter_bonus"] = base.get("counter_bonus", 0) + 8
    late["attack_fraction"] = min(0.98, base.get("attack_fraction", 0.85) + 0.12)
    late["comet_bonus"] = max(0, base.get("comet_bonus", 10) - 5)

    return {"early": early, "mid": mid, "late": late}


PARAMS_CONFIG = generate_phase_configs(BASE_PARAMS)

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_RADIUS = 10.0
MAX_FLEET_SPEED = 6.0

def dist_xy(x1, y1, x2, y2):
    return math.hypot(x1 - x2, y1 - y2)

def segment_point_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def path_hits_sun(sx, sy, tx, ty):
    return segment_point_distance(CENTER_X, CENTER_Y, sx, sy, tx, ty) <= SUN_RADIUS + 0.5

def fleet_speed(ships):
    if ships <= 1:
        return 1.0
    return min(MAX_FLEET_SPEED, 1.0 + 5.0 * (math.log(ships) / math.log(1000)) ** 1.5)

def travel_time(distance, ships):
    return distance / fleet_speed(ships) if ships > 0 else 999.0

def predict_pos(pid, at_step, orbit_table):
    info = orbit_table.get(pid)
    if not info:
        return None
    angle = info["a0"] + info["av"] * at_step
    return (CENTER_X + info["r"] * math.cos(angle),
            CENTER_Y + info["r"] * math.sin(angle))

def aim_angle(src, target, send_ships, step, orbit_table):
    tx, ty = target["x"], target["y"]
    if target["id"] in orbit_table:
        for _ in range(2):
            d = dist_xy(src["x"], src["y"], tx, ty)
            tt = travel_time(d, send_ships)
            pred = predict_pos(target["id"], step + tt, orbit_table)
            if pred:
                tx, ty = pred
        if path_hits_sun(src["x"], src["y"], tx, ty):
            tx, ty = target["x"], target["y"]
    return math.atan2(ty - src["y"], tx - src["x"])

EARLY_END = 80
MID_END = 280

def parse_planet(p):
    return {
        "id": p[0], "owner": p[1], "x": p[2], "y": p[3],
        "radius": p[4], "ships": p[5], "production": p[6],
    }

def parse_fleet(f):
    return {
        "id": f[0], "owner": f[1], "x": f[2], "y": f[3],
        "angle": f[4], "from_planet": f[5], "ships": f[6],
    }

def build_orbit_table(initial_planets, angular_velocity):
    table = {}
    for p in initial_planets:
        pid, ix, iy, radius = p[0], p[2], p[3], p[4]
        orbital_r = dist_xy(ix, iy, CENTER_X, CENTER_Y)
        if orbital_r > 0.1 and orbital_r + radius < 50.0:
            table[pid] = {
                "r": orbital_r,
                "a0": math.atan2(iy - CENTER_Y, ix - CENTER_X),
                "av": angular_velocity,
            }
    return table

def static_fleet_hit_eta(fx, fy, fdx, fdy, speed, planet, max_steps=None):
    px, py = planet["x"], planet["y"]
    vx, vy = speed * fdx, speed * fdy
    rx, ry = fx - px, fy - py
    hit_radius = planet["radius"] + 2.5
    a = vx * vx + vy * vy
    b = 2.0 * (rx * vx + ry * vy)
    c = rx * rx + ry * ry - hit_radius * hit_radius
    disc = b * b - 4.0 * a * c
    if a <= 0 or disc <= 0:
        return None

    root = math.sqrt(disc)
    t_enter = (-b - root) / (2.0 * a)
    t_exit = (-b + root) / (2.0 * a)
    if t_exit <= 0:
        return None

    if max_steps is None:
        return max(0.0, t_enter)

    eta = max(1, int(math.floor(t_enter)) + 1)
    return eta if eta <= max_steps and eta < t_exit else None


def orbit_band_possible(fx, fy, fdx, fdy, speed, planet, orbit_table, max_steps):
    info = orbit_table.get(planet["id"])
    if not info:
        return True

    travel = max_steps * speed
    end_x = fx + travel * fdx
    end_y = fy + travel * fdy
    min_center_dist = segment_point_distance(CENTER_X, CENTER_Y, fx, fy, end_x, end_y)
    max_center_dist = max(dist_xy(fx, fy, CENTER_X, CENTER_Y), dist_xy(end_x, end_y, CENTER_X, CENTER_Y))
    hit_radius = planet["radius"] + 2.5
    orbit_r = info["r"]
    return max_center_dist >= orbit_r - hit_radius and min_center_dist <= orbit_r + hit_radius


def cached_predict_pos(pid, at_step, orbit_table, eta_cache=None):
    if eta_cache is None:
        return predict_pos(pid, at_step, orbit_table)

    cache_key = ("pos", pid, at_step)
    if cache_key not in eta_cache:
        eta_cache[cache_key] = predict_pos(pid, at_step, orbit_table)
    return eta_cache[cache_key]


def cached_orbit_path(pid, step, orbit_table, max_steps, eta_cache=None):
    info = orbit_table.get(pid)
    if not info:
        return None

    if eta_cache is None:
        base_angle = info["a0"] + info["av"] * step
        return [
            (
                CENTER_X + info["r"] * math.cos(base_angle + info["av"] * eta),
                CENTER_Y + info["r"] * math.sin(base_angle + info["av"] * eta),
            )
            for eta in range(1, max_steps + 1)
        ]

    cache_key = ("path", pid, step, max_steps)
    if cache_key not in eta_cache:
        base_angle = info["a0"] + info["av"] * step
        eta_cache[cache_key] = [
            (
                CENTER_X + info["r"] * math.cos(base_angle + info["av"] * eta),
                CENTER_Y + info["r"] * math.sin(base_angle + info["av"] * eta),
            )
            for eta in range(1, max_steps + 1)
        ]
    return eta_cache[cache_key]


def fleet_hit_eta(fleet, planet, step=None, orbit_table=None, max_steps=120, eta_cache=None):
    cache_key = None
    if eta_cache is not None:
        cache_key = (fleet["owner"], fleet["id"], planet["id"], step, max_steps)
        if cache_key in eta_cache:
            return eta_cache[cache_key]

    def remember(value):
        if cache_key is not None:
            eta_cache[cache_key] = value
        return value

    fx, fy = fleet["x"], fleet["y"]
    fdx = math.cos(fleet["angle"])
    fdy = math.sin(fleet["angle"])
    speed = fleet_speed(fleet["ships"])
    if speed <= 0:
        return remember(None)

    if step is not None and orbit_table is not None:
        if planet["id"] not in orbit_table:
            return remember(static_fleet_hit_eta(fx, fy, fdx, fdy, speed, planet, max_steps=max_steps))
        if not orbit_band_possible(fx, fy, fdx, fdy, speed, planet, orbit_table, max_steps):
            return remember(None)

        orbit_path = cached_orbit_path(planet["id"], step, orbit_table, max_steps, eta_cache=eta_cache)
        hit_radius_sq = (planet["radius"] + 2.5) ** 2
        step_dx = speed * fdx
        step_dy = speed * fdy
        fleet_x, fleet_y = fx, fy
        for eta, (px, py) in enumerate(orbit_path, 1):
            fleet_x += step_dx
            fleet_y += step_dy
            dx = fleet_x - px
            dy = fleet_y - py
            if dx * dx + dy * dy < hit_radius_sq:
                return remember(eta)
        return remember(None)

    return remember(static_fleet_hit_eta(fx, fy, fdx, fdy, speed, planet))


def detect_threats(my_planets, enemy_fleets, step=None, orbit_table=None, eta_cache=None):
    threats = {}
    for fleet in enemy_fleets:
        for planet in my_planets:
            if fleet_hit_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache) is not None:
                threats[planet["id"]] = threats.get(planet["id"], 0) + fleet["ships"]
    return threats


def detect_reinforcements(my_planets, my_fleets, step=None, orbit_table=None, eta_cache=None):
    reinforcements = {}
    for fleet in my_fleets:
        for planet in my_planets:
            if fleet_hit_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache) is not None:
                reinforcements[planet["id"]] = reinforcements.get(planet["id"], 0) + fleet["ships"]
    return reinforcements


def detect_threats_detailed(my_planets, enemy_fleets, step=None, orbit_table=None, eta_cache=None):
    details = {}
    for fleet in enemy_fleets:
        for planet in my_planets:
            eta = fleet_hit_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache)
            if eta is not None:
                if planet["id"] not in details:
                    details[planet["id"]] = []
                details[planet["id"]].append((fleet["ships"], eta))
    return details


def detect_reinforcements_detailed(my_planets, my_fleets, step=None, orbit_table=None, eta_cache=None):
    details = {}
    for fleet in my_fleets:
        for planet in my_planets:
            eta = fleet_hit_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache)
            if eta is not None:
                if planet["id"] not in details:
                    details[planet["id"]] = []
                details[planet["id"]].append((fleet["ships"], eta))
    return details

def get_phase_params(step, params_config):
    if step < EARLY_END:
        return params_config["early"]
    elif step < MID_END:
        return params_config["mid"]
    else:
        return params_config["late"]


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
def reserve_for(src, threat, P):
    reserve = max(P["min_reserve"], int(src["production"] * P["reserve_prod_mult"]))
    if threat:
        reserve += int(threat * P["panic_reserve_mult"])
    return reserve


def reinforce_targets(my_planets, threats, P):
    targets = []
    for planet in my_planets:
        incoming = threats.get(planet["id"], 0)
        if incoming > max(5, planet["ships"] * 0.35):
            deficit = incoming - planet["ships"] * 0.25
            worth_limit = planet["production"] * P.get("defense_worth_factor", 10.0)
            if deficit > worth_limit:
                continue
            urgency = deficit * (1.0 + planet["production"] * 0.5)
            targets.append((urgency, planet))
    targets.sort(key=lambda item: item[0], reverse=True)
    return [planet for _, planet in targets]


def identify_doomed_planets(my_planets, threats_det, reinforcements_det, is_behind, P):
    doomed_planets = set()
    for p in my_planets:
        pid = p["id"]
        p_threats = threats_det.get(pid, [])
        if not p_threats:
            continue
        p_threats.sort(key=lambda x: x[1])
        earliest_eta = p_threats[0][1]
        incoming_enemy = sum(x[0] for x in p_threats if x[1] <= earliest_eta + 1.5)
        p_reinf = reinforcements_det.get(pid, [])
        incoming_friendly = sum(x[0] for x in p_reinf if x[1] <= earliest_eta + 0.5)
        max_possible_defenders = p["ships"] + int(earliest_eta * p["production"]) + incoming_friendly

        deficit = incoming_enemy - max_possible_defenders
        worth_limit = p["production"] * P.get("defense_worth_factor", 10.0)

        is_minor = p["production"] <= int(P.get("evac_minor_prod", 2.0))
        evac_eta = P.get("evac_eta_threshold", 3.0)
        if (incoming_enemy > max_possible_defenders and earliest_eta <= evac_eta) or (deficit > worth_limit and earliest_eta <= evac_eta + 1.0):
            if is_behind or is_minor:
                doomed_planets.add(pid)
    return doomed_planets


def build_net_threats(my_planets, threats, reinforcements):
    net_threats = {}
    for p in my_planets:
        pid = p["id"]
        net_threats[pid] = max(0, threats.get(pid, 0) - reinforcements.get(pid, 0))
    return net_threats


def fleet_hits_planet_eta(fleet, planet, step, orbit_table, max_steps=120, eta_cache=None):
    return fleet_hit_eta(fleet, planet, step, orbit_table, max_steps=max_steps, eta_cache=eta_cache)


def detect_counter_attack_targets(enemy_fleets, my_planets, step, orbit_table, eta_cache=None):
    counter_attack_targets = set()
    for fleet in enemy_fleets:
        if fleet["from_planet"] < 0:
            continue
        for planet in my_planets:
            if fleet_hits_planet_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache) is not None:
                counter_attack_targets.add(fleet["from_planet"])
                break
    return counter_attack_targets



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


def run_feint(attack_targets, my_planets, my_fleets, late_game_behind, step, P, orbit_table, doomed_planets, moves, eta_cache=None):
    if not late_game_behind or (step % int(P.get("feint_interval", 6.0)) != 0):
        return

    enemy_fortresses = [p for p in attack_targets if p["owner"] != -1]
    enemy_fortresses.sort(key=lambda p: (-p["production"], -p["ships"]))

    feint_executed = False
    for target in enemy_fortresses:
        if feint_executed:
            break

        already_has_fleet = False
        for fleet in my_fleets:
            if fleet["ships"] < 1:
                continue
            if fleet_hits_planet_eta(fleet, target, step, orbit_table, eta_cache=eta_cache) is not None:
                already_has_fleet = True
                break

        if already_has_fleet:
            continue

        for src in my_planets:
            if src["id"] in doomed_planets:
                continue
            if src["ships"] < P["min_ships"] + int(P.get("feint_min_margin", 2.0)):
                continue

            if path_hits_sun(src["x"], src["y"], target["x"], target["y"]):
                continue

            angle = aim_angle(src, target, 1, step, orbit_table)
            moves.append([src["id"], angle, 1])
            src["ships"] -= 1
            feint_executed = True
            break


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


def agent(obs):
    player = obs.get("player", 0)
    step = obs.get("step", 0)
    planets = [parse_planet(p) for p in obs.get("planets", [])]
    fleets = [parse_fleet(f) for f in obs.get("fleets", [])]
    angular_velocity = obs.get("angular_velocity", 0.0)
    initial_planets = obs.get("initial_planets", [])
    comet_ids = set(obs.get("comet_planet_ids", []))

    orbit_table = build_orbit_table(initial_planets, angular_velocity)
    my_planets = [p for p in planets if p["owner"] == player]
    enemy_fleets = [f for f in fleets if f["owner"] != player]
    my_fleets = [f for f in fleets if f["owner"] == player]
    attack_targets = [p for p in planets if p["owner"] != player]

    my_total_ships = sum(p["ships"] for p in my_planets) + sum(f["ships"] for f in my_fleets)
    enemy_total_ships = sum(p["ships"] for p in attack_targets if p["owner"] != -1) + sum(f["ships"] for f in enemy_fleets)
    my_prod = sum(p["production"] for p in my_planets)
    enemy_prod = sum(p["production"] for p in attack_targets if p["owner"] != -1)
    is_behind = (my_prod < enemy_prod * 1.1) or (my_total_ships < enemy_total_ships * 1.1)

    P = get_phase_params(step, PARAMS_CONFIG)
    late_game_ahead = (step >= MID_END) and (not is_behind)
    late_game_behind = (step >= MID_END) and is_behind
    honeypot_id = choose_honeypot(my_planets, late_game_ahead, P)
    eta_cache = {}

    if not my_planets or not attack_targets:
        return []

    threats = detect_threats(my_planets, enemy_fleets, step, orbit_table, eta_cache=eta_cache)
    reinforcements = detect_reinforcements(my_planets, my_fleets, step, orbit_table, eta_cache=eta_cache)
    threats_det = detect_threats_detailed(my_planets, enemy_fleets, step, orbit_table, eta_cache=eta_cache)
    reinforcements_det = detect_reinforcements_detailed(my_planets, my_fleets, step, orbit_table, eta_cache=eta_cache)
    doomed_planets = identify_doomed_planets(my_planets, threats_det, reinforcements_det, is_behind, P)
    net_threats = build_net_threats(my_planets, threats, reinforcements)
    counter_attack_targets = detect_counter_attack_targets(enemy_fleets, my_planets, step, orbit_table, eta_cache=eta_cache)

    moves = []
    assigned = {}

    run_snipe_hijack(
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
        eta_cache=eta_cache,
    )
    run_honeypot_trap(
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
    )
    run_feint(
        attack_targets,
        my_planets,
        my_fleets,
        late_game_behind,
        step,
        P,
        orbit_table,
        doomed_planets,
        moves,
        eta_cache=eta_cache,
    )
    run_pressure_plan(
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
        eta_cache=eta_cache,
    )

    return moves