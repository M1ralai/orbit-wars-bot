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
            worth_limit = planet["production"] * P.get("defense_worth_factor", 10.0)
            if deficit > worth_limit:
                continue
            urgency = deficit * (1.0 + planet["production"] * 0.5)
            targets.append((urgency, planet))
    targets.sort(key=lambda item: item[0], reverse=True)
    return [planet for _, planet in targets]


def identify_doomed_planets(my_planets, threats_det, reinforcements_det, is_behind, P):
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

        deficit = incoming_enemy - max_possible_defenders
        worth_limit = p["production"] * P.get("defense_worth_factor", 10.0)

        is_minor = p["production"] <= int(P.get("evac_minor_prod", 2.0))
        evac_eta = P.get("evac_eta_threshold", 3.0)
        if (incoming_enemy > max_possible_defenders and earliest_eta <= evac_eta) or (deficit > worth_limit and earliest_eta <= evac_eta + 1.0):
            if is_behind or is_minor:
                doomed_planets.add(pid)
    return doomed_planets


def build_net_threats(my_planets, threats, reinforcements):
    net_threats = {}
    for p in my_planets:
        pid = p["id"]
        net_threats[pid] = max(0, threats.get(pid, 0) - reinforcements.get(pid, 0))
    return net_threats
