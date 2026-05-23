from bot.state import parse_planet, parse_fleet, build_orbit_table, detect_threats, get_phase_params
from bot.scoring import capture_cost, score_target
from bot.geometry import aim_angle, dist_xy, path_hits_sun
from bot.params import PARAMS_CONFIG


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
