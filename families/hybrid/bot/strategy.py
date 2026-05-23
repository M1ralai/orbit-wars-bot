import math
from bot.state import parse_planet, parse_fleet, build_orbit_table, detect_threats, detect_reinforcements, detect_threats_detailed, detect_reinforcements_detailed, get_phase_params, EARLY_END, MID_END
from bot.scoring import capture_cost, score_target
from bot.geometry import aim_angle, dist_xy, path_hits_sun, fleet_speed, travel_time, predict_pos
from bot.params import PARAMS_CONFIG


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
