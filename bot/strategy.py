from bot.state import parse_planet, parse_fleet, build_orbit_table, detect_threats, get_phase_params
from bot.scoring import capture_cost, score_target
from bot.geometry import aim_angle
from bot.params import PARAMS_CONFIG

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
