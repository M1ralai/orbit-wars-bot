import math
# Counterwave is intentionally not an eco-first family. It keeps a thicker
# reserve, taxes neutral expansion, and looks for short enemy/counter punches.
BASE_PARAMS = {
    "min_ships": 12,
    "min_reserve": 6,
    "reserve_prod_mult": 4.6583,
    "panic_reserve_mult": 1.2502,
    "neutral_bonus": -2,
    "neutral_tax": 18,
    "enemy_bonus": 46,
    "enemy_weak_bonus": 1.5952,
    "counter_bonus": 24,
    "pressure_max": 32,
    "pressure_divisor": 21,
    "production_weight": 15,
    "high_production_weight": 46,
    "high_prod_tax": 19,
    "distance_weight": 3.6553,
    "high_distance_weight": 2.1815,
    "short_hop_bonus": 0.3382,
    "short_hop_range": 21,
    "ship_weight": 0.7761,
    "high_ship_weight": 0.5,
    "overkill": 8,
    "high_prod_extra": 0,
    "enemy_extra": 7,
    "attack_fraction": 0.665,
    "max_attacks_per_turn": 1,
    "comet_bonus": -8,
}


def generate_phase_configs(base):
    early = dict(base)
    early["enemy_bonus"] = max(0, base["enemy_bonus"] - 8)
    early["neutral_bonus"] = base["neutral_bonus"] + 5
    early["neutral_tax"] = max(0, base["neutral_tax"] - 5)
    early["pressure_max"] = max(0, base["pressure_max"] - 16)
    early["attack_fraction"] = min(0.72, base["attack_fraction"] + 0.08)
    early["comet_bonus"] = base["comet_bonus"] + 4

    mid = dict(base)

    late = dict(base)
    late["enemy_bonus"] = base["enemy_bonus"] + 14
    late["neutral_tax"] = base["neutral_tax"] + 8
    late["pressure_max"] = base["pressure_max"] + 18
    late["counter_bonus"] = base["counter_bonus"] + 8
    late["attack_fraction"] = min(0.82, base["attack_fraction"] + 0.12)

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


def score_target(src, target, player, step, assigned, P, comet_ids, orbit_table, threats):
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

    return (
        target["production"] * prod_w
        + owner_score
        + local_bonus
        + comet_bonus
        - high_prod_tax
        - distance * dist_w
        - needed * ship_w
    )


def reserve_for(src, threat, P):
    reserve = max(P["min_reserve"], int(src["production"] * P["reserve_prod_mult"]))
    if threat:
        reserve += int(threat * P["panic_reserve_mult"])
    return reserve


def reinforce_targets(my_planets, threats):
    targets = []
    for planet in my_planets:
        incoming = threats.get(planet["id"], 0)
        if incoming > max(5, planet["ships"] * 0.35):
            targets.append((incoming - planet["ships"] * 0.25, planet))
    targets.sort(key=lambda item: item[0], reverse=True)
    return [planet for _, planet in targets]


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
    attack_targets = [p for p in planets if p["owner"] != player]

    if not my_planets or not attack_targets:
        return []

    threats = detect_threats(my_planets, enemy_fleets)
    P = get_phase_params(step, PARAMS_CONFIG)
    moves = []
    assigned = {}
    attacks = 0

    my_planets.sort(
        key=lambda p: (
            threats.get(p["id"], 0) <= 0,
            p["ships"],
            p["production"],
        ),
        reverse=True,
    )

    threatened_homes = reinforce_targets(my_planets, threats)
    for src in my_planets:
        threat = threats.get(src["id"], 0)
        reserve = reserve_for(src, threat, P)
        available = int(src["ships"] - reserve)
        if available <= P["min_ships"]:
            continue

        for home in threatened_homes[:2]:
            if home["id"] == src["id"] or path_hits_sun(src["x"], src["y"], home["x"], home["y"]):
                continue
            if dist_xy(src["x"], src["y"], home["x"], home["y"]) > P["short_hop_range"] * 1.7:
                continue
            send = min(available // 2, max(4, int(threats.get(home["id"], 0) * 0.7)))
            if send <= 0:
                continue
            moves.append([src["id"], aim_angle(src, home, send, step, orbit_table), send])
            available -= send
            break

        if attacks >= P["max_attacks_per_turn"] or available <= P["min_ships"]:
            continue

        scored = []
        for target in attack_targets:
            score = score_target(src, target, player, step, assigned, P, comet_ids, orbit_table, threats)
            if score > -1e8:
                scored.append((score, target))

        scored.sort(key=lambda item: item[0], reverse=True)
        for score, target in scored[:3]:
            if score < 0 or attacks >= P["max_attacks_per_turn"]:
                break

            needed = capture_cost(target, player, assigned, P)
            budget = max(1, int(available * P["attack_fraction"]))
            send = min(available, budget, needed)
            remaining = target["ships"] - assigned.get(target["id"], 0)
            if send <= remaining:
                continue

            moves.append([src["id"], aim_angle(src, target, send, step, orbit_table), send])
            assigned[target["id"]] = assigned.get(target["id"], 0) + send
            available -= send
            attacks += 1
            break

    return moves