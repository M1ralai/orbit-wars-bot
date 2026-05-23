import math
# Counterwave is intentionally not an eco-first family. It keeps a thicker
# reserve, taxes neutral expansion, and looks for short enemy/counter punches.
BASE_PARAMS = {
    "min_ships": 13,
    "min_reserve": 5,
    "reserve_prod_mult": 2.6,
    "panic_reserve_mult": 0.853,
    "neutral_bonus": 13,
    "neutral_tax": 4,
    "enemy_bonus": 37,
    "enemy_weak_bonus": 0.7892,
    "counter_bonus": 22,
    "pressure_max": 0,
    "pressure_divisor": 31,
    "production_weight": 28,
    "high_production_weight": 43,
    "high_prod_tax": 10,
    "distance_weight": 2.3219,
    "high_distance_weight": 2.3219,
    "short_hop_bonus": 2.0581,
    "short_hop_range": 31,
    "ship_weight": 1.2,
    "high_ship_weight": 1.1787,
    "overkill": 4,
    "high_prod_extra": 5,
    "enemy_extra": 8,
    "attack_fraction": 0.8943,
    "max_attacks_per_turn": 4,
    "comet_bonus": 11,
    "staging_penalty": 15.0,
    "defense_worth_factor": 10.0,
    "counter_attack_bonus": 23.5705,
    "production_forecast_mult": 1.0,
    "evac_eta_threshold": 4.1462,
    "evac_minor_prod": 3,
    "sync_max_eta": 13.2068,
    "sync_min_target_prod": 3,
    "sync_min_target_ships": 34,
    "snipe_max_step": 112,
    "snipe_overkill": 5,
    "honeypot_min_prod": 5,
    "honeypot_reserve": 6,
    "feint_interval": 8,
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


def detect_reinforcements(my_planets, my_fleets):
    reinforcements = {}
    for fleet in my_fleets:
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
                reinforcements[planet["id"]] = reinforcements.get(planet["id"], 0) + fleet["ships"]
    return reinforcements


def detect_threats_detailed(my_planets, enemy_fleets):
    details = {}
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
                d = dist_xy(fx, fy, px, py)
                speed = fleet_speed(fleet["ships"])
                eta = d / speed if speed > 0 else 999.0
                if planet["id"] not in details:
                    details[planet["id"]] = []
                details[planet["id"]].append((fleet["ships"], eta))
    return details


def detect_reinforcements_detailed(my_planets, my_fleets):
    details = {}
    for fleet in my_fleets:
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
                d = dist_xy(fx, fy, px, py)
                speed = fleet_speed(fleet["ships"])
                eta = d / speed if speed > 0 else 999.0
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
            # Tactical Defense Abandonment if cost is too high relative to production
            worth_limit = planet["production"] * P.get("defense_worth_factor", 10.0)
            if deficit > worth_limit:
                continue
            # Worth-weighted Prioritization
            urgency = deficit * (1.0 + planet["production"] * 0.5)
            targets.append((urgency, planet))
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

    honeypot_id = None
    if late_game_ahead:
        min_prod = int(P.get("honeypot_min_prod", 3.0))
        candidates = [p for p in my_planets if p["production"] >= min_prod]
        if not candidates:
            candidates = [p for p in my_planets if p["production"] >= max(1, min_prod - 1)]
        if candidates:
            candidates.sort(key=lambda p: (-p["production"], p["id"]))
            honeypot_id = candidates[0]["id"]
    if not my_planets or not attack_targets:
        return []

    threats = detect_threats(my_planets, enemy_fleets)
    reinforcements = detect_reinforcements(my_planets, my_fleets)
    threats_det = detect_threats_detailed(my_planets, enemy_fleets)
    reinforcements_det = detect_reinforcements_detailed(my_planets, my_fleets)

    # 1. Identify doomed planets for Tactical Retreat / Evacuation
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
        
        deficit = incoming_enemy - p["ships"] * 0.25
        worth_limit = p["production"] * P.get("defense_worth_factor", 10.0)
        
        is_minor = p["production"] <= int(P.get("evac_minor_prod", 2.0))
        evac_eta = P.get("evac_eta_threshold", 3.0)
        if (incoming_enemy > max_possible_defenders and earliest_eta <= evac_eta) or (deficit > worth_limit and earliest_eta <= evac_eta + 1.0):
            if is_behind or is_minor:
                doomed_planets.add(pid)

    net_threats = {}
    for p in my_planets:
        pid = p["id"]
        net_threats[pid] = max(0, threats.get(pid, 0) - reinforcements.get(pid, 0))

    # Detect enemy launchpads heading to our planets (for Counter-Attack target tracking)
    counter_attack_targets = set()
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
                if fleet["from_planet"] >= 0:
                    counter_attack_targets.add(fleet["from_planet"])

    moves = []
    assigned = {}
    attacks = 0

    # Tactic 2: Snipe / Capture Hijacking (Only in early game)
    early_game = (step < P.get("snipe_max_step", 90.0))
    if early_game:
        # Scan neutral planets targeted by enemy fleets
        for target in attack_targets:
            if target["owner"] != -1:  # Must be neutral
                continue
            
            # Find enemy fleets targeting this neutral planet
            target_enemy_fleets = []
            for fleet in enemy_fleets:
                speed = fleet_speed(fleet["ships"])
                if speed <= 0:
                    continue
                
                angle = fleet["angle"]
                fx, fy = fleet["x"], fleet["y"]
                arrival_step = None
                
                # Check next 60 turns
                for t in range(step + 1, step + 61):
                    # Enemy position at step t
                    curr_fx = fx + (t - step) * speed * math.cos(angle)
                    curr_fy = fy + (t - step) * speed * math.sin(angle)
                    # Planet position at step t
                    px, py = predict_pos(target["id"], t, orbit_table) if target["id"] in orbit_table else (target["x"], target["y"])
                    
                    if dist_xy(curr_fx, curr_fy, px, py) < target["radius"] + 2.5:
                        arrival_step = t
                        break
                
                if arrival_step is not None:
                    target_enemy_fleets.append((fleet["ships"], arrival_step))
            
            if not target_enemy_fleets:
                continue
            
            # Find earliest enemy arrival
            target_enemy_fleets.sort(key=lambda x: x[1])
            enemy_ships, K = target_enemy_fleets[0]
            
            # Can the enemy capture the neutral planet?
            neutral_ships = target["ships"]
            if enemy_ships > neutral_ships:
                # Enemy captures at step K
                enemy_surviving = enemy_ships - neutral_ships
                # Target arrival step for us is K + 1
                A_target = K + 1
                
                # Predict target position at A_target
                pred = predict_pos(target["id"], A_target, orbit_table) if target["id"] in orbit_table else (target["x"], target["y"])
                
                # Find out enemy ships at A_target (includes 1 turn of production)
                enemy_total = enemy_surviving + target["production"]
                # Required ships to conquer
                S_needed = enemy_total + P.get("snipe_overkill", 3.0)
                
                # Find all our planets that can reach this target at exactly A_target
                valid_snipers = []
                for src in my_planets:
                    if src["id"] in doomed_planets:
                        continue
                    
                    threat = net_threats.get(src["id"], 0)
                    reserve = reserve_for(src, threat, P)
                    available = int(src["ships"] - reserve)
                    if available <= 0:
                        continue
                    
                    # Path must not hit sun
                    if path_hits_sun(src["x"], src["y"], pred[0], pred[1]):
                        continue
                    
                    # Calculate ETA
                    d0 = dist_xy(src["x"], src["y"], pred[0], pred[1])
                    tt = travel_time(d0, S_needed)
                    eta = int(0.5 + tt)
                    
                    if step + eta == A_target:
                        valid_snipers.append((src, available))
                
                # Do we have enough total available ships across valid snipers?
                total_avail = sum(avail for _, avail in valid_snipers)
                if total_avail >= S_needed:
                    remaining_needed = S_needed
                    for src, avail in valid_snipers:
                        if remaining_needed <= 0:
                            break
                        send = min(avail, remaining_needed)
                        if send > 0:
                            angle = math.atan2(pred[1] - src["y"], pred[0] - src["x"])
                            moves.append([src["id"], angle, send])
                            assigned[target["id"]] = assigned.get(target["id"], 0) + send
                            remaining_needed -= send
                            src["ships"] -= send

    # Tactic 1: Honeypot Trap Spring (Only in late game when ahead)
    if late_game_ahead and honeypot_id is not None and threats_det.get(honeypot_id, []):
        p_threats = list(threats_det[honeypot_id])
        p_threats.sort(key=lambda x: x[1])
        enemy_ships, K = p_threats[0]
        
        hp_planet = next((p for p in my_planets if p["id"] == honeypot_id), None)
        if hp_planet:
            hp_ships_at_K = hp_planet["ships"] + int((K - step) * hp_planet["production"])
            deficit = enemy_ships - hp_ships_at_K
            
            if deficit > 0:
                needed_reinf = deficit + P.get("snipe_overkill", 3.0)
                
                # Look for neighboring planets to reinforce exactly at step K
                for neighbor in my_planets:
                    if neighbor["id"] == honeypot_id or neighbor["id"] in doomed_planets:
                        continue
                    
                    neigh_threat = net_threats.get(neighbor["id"], 0)
                    neigh_res = reserve_for(neighbor, neigh_threat, P)
                    neigh_avail = int(neighbor["ships"] - neigh_res)
                    if neigh_avail <= 0:
                        continue
                    
                    # Predict position of honeypot at K
                    pred_hp = predict_pos(honeypot_id, K, orbit_table) if honeypot_id in orbit_table else (hp_planet["x"], hp_planet["y"])
                    
                    # Path must not hit sun
                    if path_hits_sun(neighbor["x"], neighbor["y"], pred_hp[0], pred_hp[1]):
                        continue
                    
                    d0 = dist_xy(neighbor["x"], neighbor["y"], pred_hp[0], pred_hp[1])
                    tt = travel_time(d0, needed_reinf)
                    eta = int(0.5 + tt)
                    
                    if step + eta == K:
                        send = min(neigh_avail, needed_reinf)
                        if send > 0:
                            angle = math.atan2(pred_hp[1] - neighbor["y"], pred_hp[0] - neighbor["x"])
                            moves.append([neighbor["id"], angle, send])
                            needed_reinf -= send
                            neighbor["ships"] -= send
                            net_threats[honeypot_id] = max(0, net_threats.get(honeypot_id, 0) - send)

    # Tactic 3: Sahte Kuşatma / Feint (Only in late game when behind)
    if late_game_behind and (step % int(P.get("feint_interval", 6.0)) == 0):
        enemy_fortresses = [p for p in attack_targets if p["owner"] not in (-1, player)]
        enemy_fortresses.sort(key=lambda p: (-p["production"], -p["ships"]))
        
        feint_executed = False
        for target in enemy_fortresses:
            if feint_executed:
                break
            
            already_has_fleet = False
            for fleet in my_fleets:
                if fleet["ships"] >= 1:
                    fx, fy = fleet["x"], fleet["y"]
                    fdx, fdy = math.cos(fleet["angle"]), math.sin(fleet["angle"])
                    vpx, vpy = target["x"] - fx, target["y"] - fy
                    dot = vpx * fdx + vpy * fdy
                    if dot > 0:
                        perp = abs(vpx * fdy - vpy * fdx)
                        if perp < target["radius"] + 2.5:
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

    my_planets.sort(
        key=lambda p: (
            net_threats.get(p["id"], 0) <= 0,
            p["ships"],
            p["production"],
        ),
        reverse=True,
    )

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

        # Try to reinforce or evacuate
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
            if bridge_id is not None:
                bridge_planet = next((p for p in my_planets if p["id"] == bridge_id), None)
                if bridge_planet:
                    aim_target = bridge_planet
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

            # 3. Coordinated Sync Attack (Time-on-Target) check
            incoming_friendly_etas = []
            for fleet in my_fleets:
                if fleet["ships"] < 4:
                    continue
                fx, fy = fleet["x"], fleet["y"]
                fdx = math.cos(fleet["angle"])
                fdy = math.sin(fleet["angle"])
                vpx, vpy = target["x"] - fx, target["y"] - fy
                dot = vpx * fdx + vpy * fdy
                if dot <= 0:
                    continue
                perp = abs(vpx * fdy - vpy * fdx)
                if perp < target["radius"] + 2.5:
                    d = dist_xy(fx, fy, target["x"], target["y"])
                    speed = fleet_speed(fleet["ships"])
                    eta = d / speed if speed > 0 else 999.0
                    incoming_friendly_etas.append(eta)

            target_max_eta = max(incoming_friendly_etas) if incoming_friendly_etas else 0.0
            
            # Only hold launch for normal attacks against major/fortified targets to preserve expansion tempo
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
            assigned[target["id"]] = assigned.get(target["id"], 0) + send
            available -= send
            attacks += 1

    return moves