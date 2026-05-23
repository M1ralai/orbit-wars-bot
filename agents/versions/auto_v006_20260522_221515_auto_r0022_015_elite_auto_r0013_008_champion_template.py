import math
# The base parameters injected by auto_iterate
BASE_PARAMS = {
    "min_ships": 14,
    "min_reserve": 2,
    "reserve_prod_mult": 1.8,
    "neutral_bonus": 25,
    "enemy_bonus": 23,
    "pressure_max": 2,
    "pressure_divisor": 18,
    "production_weight": 48,
    "high_production_weight": 63,
    "distance_weight": 2.3995,
    "high_distance_weight": 2.1332,
    "ship_weight": 1.2958,
    "high_ship_weight": 1.03,
    "overkill": 5,
    "high_prod_extra": 0,
    "enemy_extra": 7,
    "comet_bonus": 10,
}

def generate_phase_configs(base):
    # Derive phases from the mutated base parameters
    early = dict(base)
    early["min_ships"] = max(2, base["min_ships"] - 3)
    early["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.4)
    early["neutral_bonus"] = base["neutral_bonus"] + 15
    early["pressure_max"] = 0
    early["comet_bonus"] = 15

    mid = dict(base)
    mid["enemy_bonus"] = base["enemy_bonus"] + 10
    mid["pressure_max"] = base["pressure_max"] + 4

    late = dict(base)
    late["min_ships"] = max(2, base["min_ships"] - 2)
    late["reserve_prod_mult"] = max(1.0, base["reserve_prod_mult"] - 0.6)
    late["neutral_bonus"] = max(0, base["neutral_bonus"] - 3)
    late["enemy_bonus"] = base["enemy_bonus"] + 20
    late["pressure_max"] = base["pressure_max"] + 12
    late["comet_bonus"] = 5

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

def detect_threats(my_planets, enemy_fleets):
    threats = {}
    for fleet in enemy_fleets:
        fx, fy = fleet["x"], fleet["y"]
        fdx = math.cos(fleet["angle"])
        fdy = math.sin(fleet["angle"])
        for planet in my_planets:
            px, py = planet["x"], planet["y"]
            vpx, vpy = px - fx, py - fy
            dot = vpx * fdx + vpy * fdy
            if dot <= 0:
                continue
            perp = abs(vpx * fdy - vpy * fdx)
            if perp < planet["radius"] + 2.5:
                threats[planet["id"]] = threats.get(planet["id"], 0) + fleet["ships"]
    return threats

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

    my_planets.sort(key=lambda p: p["ships"], reverse=True)

    moves = []
    assigned = {}

    for src in my_planets:
        threat = threats.get(src["id"], 0)
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