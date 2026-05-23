from bot.state import (
    parse_planet, parse_fleet, build_orbit_table,
    detect_threats, detect_threats_detailed, detect_reinforcements_detailed,
    get_phase_params,
)
from bot.params import PARAMS_CONFIG
from bot.strategies.stance import detect_stance, get_tactic_order
from bot.strategies.evacuation import find_doomed, run_evacuation
from bot.strategies.snipe import run_snipe
from bot.strategies.reinforce import run_reinforce
from bot.strategies.sync import run_sync
from bot.strategies.honeypot import run_honeypot
from bot.strategies.counter_punch import run_counter_punch
from bot.strategies.chain_expand import run_chain_expand
from bot.strategies.prod_starve import run_prod_starve
from bot.strategies.vulture import run_vulture
from bot.strategies.turtle import run_turtle
from bot.strategies.overflow import run_overflow
from bot.strategies.comet_rush import run_comet_rush
from bot.strategies.core_attack import run_core_attack


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
    my_fleets = [f for f in fleets if f["owner"] == player]

    if not my_planets or not targets:
        return []

    # --- Situation awareness ---
    eta_cache = {}
    threats = detect_threats(my_planets, enemy_fleets, step, orbit_table, eta_cache=eta_cache)
    threats_det = detect_threats_detailed(my_planets, enemy_fleets, step, orbit_table, eta_cache=eta_cache)
    reinf_det = detect_reinforcements_detailed(my_planets, my_fleets, step, orbit_table, eta_cache=eta_cache)

    P = get_phase_params(step, PARAMS_CONFIG)
    doomed = find_doomed(my_planets, threats_det, reinf_det)

    my_prod = sum(p["production"] for p in my_planets)
    enemy_prod = sum(p["production"] for p in targets if p["owner"] != -1)
    neutrals = [t for t in targets if t["owner"] == -1]
    enemy_targets = [t for t in targets if t["owner"] not in (-1, player)]

    # --- Stance detection ---
    stance = detect_stance(step, my_planets, targets, threats_det, my_prod, enemy_prod)
    tactic_order = get_tactic_order(stance)

    moves = []
    assigned = {}

    # --- Execute tactics in stance order ---
    for tactic in tactic_order:
        if tactic == "evacuation":
            run_evacuation(my_planets, doomed, step, orbit_table, moves)

        elif tactic == "snipe":
            run_snipe(neutrals, enemy_fleets, my_planets, doomed, threats,
                      step, P, orbit_table, moves, assigned)

        elif tactic == "reinforce":
            run_reinforce(my_planets, threats_det, doomed, threats,
                          step, P, orbit_table, moves)

        elif tactic == "honeypot":
            run_honeypot(my_planets, threats_det, doomed, threats,
                         my_prod, enemy_prod, step, P, orbit_table, moves)

        elif tactic == "counter_punch":
            run_counter_punch(my_planets, planets, enemy_fleets, doomed, threats,
                              player, step, P, orbit_table, moves, assigned)

        elif tactic == "chain_expand":
            run_chain_expand(my_planets, neutrals, doomed, threats,
                             player, step, P, orbit_table, moves, assigned)

        elif tactic == "prod_starve":
            run_prod_starve(my_planets, enemy_targets, doomed, threats,
                            player, step, P, orbit_table, moves, assigned)

        elif tactic == "vulture":
            run_vulture(my_planets, enemy_targets, doomed, threats,
                        player, step, P, orbit_table, moves, assigned)

        elif tactic == "turtle":
            run_turtle(my_planets, doomed, threats, step, P, orbit_table, moves)

        elif tactic == "overflow":
            run_overflow(my_planets, targets, doomed, threats,
                         player, step, P, orbit_table, moves, assigned)

        elif tactic == "comet_rush":
            run_comet_rush(my_planets, targets, comet_ids, doomed, threats,
                           player, step, P, orbit_table, moves, assigned)

        elif tactic == "core_attack":
            run_core_attack(my_planets, targets, doomed, threats,
                            player, step, P, comet_ids, orbit_table, moves, assigned)

        elif tactic == "sync":
            run_sync(my_planets, enemy_targets, doomed, threats,
                     player, step, P, orbit_table, moves, assigned)

    return moves
