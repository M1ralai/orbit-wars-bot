"""Honeypot: when ahead in late game, reinforce attacked high-value planet to crush enemy.
Guard: step >= MID_END, my_prod > 1.3x enemy_prod, highest-prod planet under attack,
       neighbors can reinforce before enemy arrives.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun, travel_time
from bot.state import MID_END
from bot.strategies.helpers import available_ships


def run_honeypot(my_planets, threats_det, doomed, threats,
                 my_prod, enemy_prod, step, P, orbit_table, moves):
    if step < MID_END or enemy_prod <= 0 or my_prod <= enemy_prod * 1.3:
        return

    # Find highest-prod planet being attacked
    best_hp, best_prod = None, 0
    for p in my_planets:
        if p["id"] in doomed:
            continue
        t_list = threats_det.get(p["id"], [])
        if not t_list:
            continue
        if p["production"] > best_prod:
            best_prod = p["production"]
            best_hp = p

    if best_hp is None or best_prod < 2:
        return

    t_list = sorted(threats_det[best_hp["id"]], key=lambda x: x[1])
    enemy_ships = sum(s for s, _ in t_list)
    earliest_eta = t_list[0][1]
    hp_at_arrival = best_hp["ships"] + int(earliest_eta * best_hp["production"])
    deficit = enemy_ships - hp_at_arrival
    if deficit <= 0:
        return

    needed = deficit + int(P["overkill"])
    for nb in my_planets:
        if nb["id"] == best_hp["id"] or nb["id"] in doomed:
            continue
        d = dist_xy(nb["x"], nb["y"], best_hp["x"], best_hp["y"])
        if d > 40:
            continue
        if path_hits_sun(nb["x"], nb["y"], best_hp["x"], best_hp["y"]):
            continue
        nb_avail = available_ships(nb, threats, P)
        if nb_avail <= 0:
            continue
        send = min(nb_avail, needed)
        tt = travel_time(d, send)
        if tt > earliest_eta:
            continue
        angle = aim_angle(nb, best_hp, send, step, orbit_table)
        moves.append([nb["id"], angle, send])
        nb["ships"] -= send
        needed -= send
        if needed <= 0:
            break
