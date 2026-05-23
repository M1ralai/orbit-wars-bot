import math
# Hybrid bot params - same core as simple bot + production_forecast_mult
BASE_PARAMS = {
    "min_ships": 19,
    "min_reserve": 3,
    "reserve_prod_mult": 1.0,
    "neutral_bonus": 26,
    "enemy_bonus": 26,
    "pressure_max": 15,
    "pressure_divisor": 34,
    "production_weight": 42,
    "high_production_weight": 49,
    "distance_weight": 2.6278,
    "high_distance_weight": 1.5487,
    "ship_weight": 1.2604,
    "high_ship_weight": 0.4604,
    "overkill": 3,
    "high_prod_extra": 6,
    "enemy_extra": 6,
    "comet_bonus": 13,
    "production_forecast_mult": 0.6229,
}


def generate_phase_configs(base):
    early = dict(base)
    early["min_ships"] = max(2, base["min_ships"] - 3)
    early["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.4)
    early["neutral_bonus"] = base["neutral_bonus"] + 15
    early["pressure_max"] = 0
    early["comet_bonus"] = base.get("comet_bonus", 10) + 5

    mid = dict(base)
    mid["enemy_bonus"] = base["enemy_bonus"] + 10
    mid["pressure_max"] = base.get("pressure_max", 0) + 4

    late = dict(base)
    late["min_ships"] = max(2, base["min_ships"] - 2)
    late["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.6)
    late["neutral_bonus"] = max(0, base["neutral_bonus"] - 3)
    late["enemy_bonus"] = base["enemy_bonus"] + 20
    late["pressure_max"] = base.get("pressure_max", 0) + 12
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


def _find_doomed(my_planets, threats, P):
    """Planets that will certainly fall - evacuate ships instead of wasting them."""
    doomed = set()
    for p in my_planets:
        threat = threats.get(p["id"], 0)
        if threat <= 0:
            continue
        can_defend = p["ships"] + p["production"] * 3
        if threat > can_defend and p["production"] <= 2:
            doomed.add(p["id"])
    return doomed


def _find_evac_target(src, my_planets, doomed, step, orbit_table):
    """Find the best nearby friendly planet to evacuate ships to."""
    best = None
    best_score = -1e9
    for p in my_planets:
        if p["id"] == src["id"] or p["id"] in doomed:
            continue
        if path_hits_sun(src["x"], src["y"], p["x"], p["y"]):
            continue
        d = dist_xy(src["x"], src["y"], p["x"], p["y"])
        score = p["production"] * 10 - d
        if score > best_score:
            best_score = score
            best = p
    return best


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
    targets = [p for p in planets if p["owner"] != player]
    enemy_fleets = [f for f in fleets if f["owner"] != player]

    if not my_planets or not targets:
        return []

    threats = detect_threats(my_planets, enemy_fleets)
    P = get_phase_params(step, PARAMS_CONFIG)
    doomed = _find_doomed(my_planets, threats, P)

    my_planets.sort(key=lambda p: p["ships"], reverse=True)

    moves = []
    assigned = {}

    for src in my_planets:
        is_doomed = src["id"] in doomed
        threat = threats.get(src["id"], 0)

        if is_doomed:
            # Evacuate: send everything to nearest friendly
            evac_target = _find_evac_target(src, my_planets, doomed, step, orbit_table)
            if evac_target and src["ships"] > 0:
                angle = aim_angle(src, evac_target, src["ships"], step, orbit_table)
                moves.append([src["id"], angle, src["ships"]])
            continue

        reserve = max(P["min_reserve"], int(src["production"] * P["reserve_prod_mult"]))
        reserve += threat

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

    return moves