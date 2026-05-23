from bot.params import PARAMS_CONFIG
from bot.state import (
    MID_END,
    build_orbit_table,
    detect_reinforcements,
    detect_reinforcements_detailed,
    detect_threats,
    detect_threats_detailed,
    get_phase_params,
    parse_fleet,
    parse_planet,
)
from bot.strategies.defense import build_net_threats, identify_doomed_planets
from bot.strategies.feint import run_feint
from bot.strategies.honeypot import choose_honeypot, run_honeypot_trap
from bot.strategies.intel import detect_counter_attack_targets
from bot.strategies.pressure import run_pressure_plan
from bot.strategies.snipe_hijack import run_snipe_hijack


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
