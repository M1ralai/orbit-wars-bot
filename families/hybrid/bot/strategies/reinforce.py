"""Reinforce: save high-value planets about to fall.
Guard: planet prod >= 3, threat within 5 steps, neighbor close + can arrive in time.
"""
from bot.geometry import aim_angle, dist_xy, path_hits_sun, travel_time
from bot.strategies.helpers import available_ships


def run_reinforce(my_planets, threats_det, doomed, threats,
                  step, P, orbit_table, moves):
    for p in my_planets:
        pid = p["id"]
        if pid in doomed or p["production"] < 3:
            continue
        t_list = threats_det.get(pid, [])
        if not t_list:
            continue
        t_sorted = sorted(t_list, key=lambda x: x[1])
        earliest_eta = t_sorted[0][1]
        if earliest_eta > 5:
            continue
        incoming_enemy = sum(s for s, e in t_sorted if e <= earliest_eta + 2)
        deficit = incoming_enemy - p["ships"] - int(earliest_eta * p["production"])
        if deficit <= 0:
            continue

        needed = deficit + int(P["overkill"])
        for nb in my_planets:
            if nb["id"] == pid or nb["id"] in doomed:
                continue
            d = dist_xy(nb["x"], nb["y"], p["x"], p["y"])
            if d > 35:
                continue
            if path_hits_sun(nb["x"], nb["y"], p["x"], p["y"]):
                continue
            nb_avail = available_ships(nb, threats, P)
            if nb_avail <= 0:
                continue
            send = min(nb_avail, needed)
            tt = travel_time(d, send)
            if tt > earliest_eta + 0.5:
                continue
            angle = aim_angle(nb, p, send, step, orbit_table)
            moves.append([nb["id"], angle, send])
            nb["ships"] -= send
            needed -= send
            if needed <= 0:
                break
