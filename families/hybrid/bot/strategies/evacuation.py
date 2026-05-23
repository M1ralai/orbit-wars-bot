"""Evacuate doomed planets — send ships to safety instead of wasting them."""
from bot.geometry import aim_angle, dist_xy, path_hits_sun


def find_doomed(my_planets, threats_det, reinf_det):
    """Identify planets that will certainly fall."""
    doomed = set()
    for p in my_planets:
        pid = p["id"]
        t_list = threats_det.get(pid, [])
        if not t_list:
            continue
        t_list_sorted = sorted(t_list, key=lambda x: x[1])
        earliest_eta = t_list_sorted[0][1]
        incoming_enemy = sum(s for s, e in t_list_sorted if e <= earliest_eta + 1.5)
        r_list = reinf_det.get(pid, [])
        incoming_friend = sum(s for s, e in r_list if e <= earliest_eta + 0.5)
        can_defend = p["ships"] + int(earliest_eta * p["production"]) + incoming_friend
        if incoming_enemy > can_defend and p["production"] <= 2 and earliest_eta <= 4:
            doomed.add(pid)
    return doomed


def _find_evac_target(src, my_planets, doomed):
    """Find best nearby friendly planet to send ships to."""
    best, best_score = None, -1e9
    for p in my_planets:
        if p["id"] == src["id"] or p["id"] in doomed:
            continue
        if path_hits_sun(src["x"], src["y"], p["x"], p["y"]):
            continue
        score = p["production"] * 10 - dist_xy(src["x"], src["y"], p["x"], p["y"])
        if score > best_score:
            best_score = score
            best = p
    return best


def run_evacuation(my_planets, doomed, step, orbit_table, moves):
    """Evacuate all doomed planets."""
    for src in my_planets:
        if src["id"] not in doomed or src["ships"] <= 0:
            continue
        evac_target = _find_evac_target(src, my_planets, doomed)
        if evac_target:
            send = src["ships"]
            angle = aim_angle(src, evac_target, send, step, orbit_table)
            moves.append([src["id"], angle, send])
            src["ships"] = 0
