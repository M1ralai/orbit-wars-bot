import math
from bot.geometry import dist_xy, segment_point_distance, CENTER_X, CENTER_Y, fleet_speed, predict_pos

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

def static_fleet_hit_eta(fx, fy, fdx, fdy, speed, planet, max_steps=None):
    px, py = planet["x"], planet["y"]
    vx, vy = speed * fdx, speed * fdy
    rx, ry = fx - px, fy - py
    hit_radius = planet["radius"] + 2.5
    a = vx * vx + vy * vy
    b = 2.0 * (rx * vx + ry * vy)
    c = rx * rx + ry * ry - hit_radius * hit_radius
    disc = b * b - 4.0 * a * c
    if a <= 0 or disc <= 0:
        return None

    root = math.sqrt(disc)
    t_enter = (-b - root) / (2.0 * a)
    t_exit = (-b + root) / (2.0 * a)
    if t_exit <= 0:
        return None

    if max_steps is None:
        return max(0.0, t_enter)

    eta = max(1, int(math.floor(t_enter)) + 1)
    return eta if eta <= max_steps and eta < t_exit else None


def orbit_band_possible(fx, fy, fdx, fdy, speed, planet, orbit_table, max_steps):
    info = orbit_table.get(planet["id"])
    if not info:
        return True

    travel = max_steps * speed
    end_x = fx + travel * fdx
    end_y = fy + travel * fdy
    min_center_dist = segment_point_distance(CENTER_X, CENTER_Y, fx, fy, end_x, end_y)
    max_center_dist = max(dist_xy(fx, fy, CENTER_X, CENTER_Y), dist_xy(end_x, end_y, CENTER_X, CENTER_Y))
    hit_radius = planet["radius"] + 2.5
    orbit_r = info["r"]
    return max_center_dist >= orbit_r - hit_radius and min_center_dist <= orbit_r + hit_radius


def cached_predict_pos(pid, at_step, orbit_table, eta_cache=None):
    if eta_cache is None:
        return predict_pos(pid, at_step, orbit_table)

    cache_key = ("pos", pid, at_step)
    if cache_key not in eta_cache:
        eta_cache[cache_key] = predict_pos(pid, at_step, orbit_table)
    return eta_cache[cache_key]


def cached_orbit_path(pid, step, orbit_table, max_steps, eta_cache=None):
    info = orbit_table.get(pid)
    if not info:
        return None

    if eta_cache is None:
        base_angle = info["a0"] + info["av"] * step
        return [
            (
                CENTER_X + info["r"] * math.cos(base_angle + info["av"] * eta),
                CENTER_Y + info["r"] * math.sin(base_angle + info["av"] * eta),
            )
            for eta in range(1, max_steps + 1)
        ]

    cache_key = ("path", pid, step, max_steps)
    if cache_key not in eta_cache:
        base_angle = info["a0"] + info["av"] * step
        eta_cache[cache_key] = [
            (
                CENTER_X + info["r"] * math.cos(base_angle + info["av"] * eta),
                CENTER_Y + info["r"] * math.sin(base_angle + info["av"] * eta),
            )
            for eta in range(1, max_steps + 1)
        ]
    return eta_cache[cache_key]


def fleet_hit_eta(fleet, planet, step=None, orbit_table=None, max_steps=120, eta_cache=None):
    cache_key = None
    if eta_cache is not None:
        cache_key = (fleet["owner"], fleet["id"], planet["id"], step, max_steps)
        if cache_key in eta_cache:
            return eta_cache[cache_key]

    def remember(value):
        if cache_key is not None:
            eta_cache[cache_key] = value
        return value

    fx, fy = fleet["x"], fleet["y"]
    fdx = math.cos(fleet["angle"])
    fdy = math.sin(fleet["angle"])
    speed = fleet_speed(fleet["ships"])
    if speed <= 0:
        return remember(None)

    if step is not None and orbit_table is not None:
        if planet["id"] not in orbit_table:
            return remember(static_fleet_hit_eta(fx, fy, fdx, fdy, speed, planet, max_steps=max_steps))
        if not orbit_band_possible(fx, fy, fdx, fdy, speed, planet, orbit_table, max_steps):
            return remember(None)

        orbit_path = cached_orbit_path(planet["id"], step, orbit_table, max_steps, eta_cache=eta_cache)
        hit_radius_sq = (planet["radius"] + 2.5) ** 2
        step_dx = speed * fdx
        step_dy = speed * fdy
        fleet_x, fleet_y = fx, fy
        for eta, (px, py) in enumerate(orbit_path, 1):
            fleet_x += step_dx
            fleet_y += step_dy
            dx = fleet_x - px
            dy = fleet_y - py
            if dx * dx + dy * dy < hit_radius_sq:
                return remember(eta)
        return remember(None)

    return remember(static_fleet_hit_eta(fx, fy, fdx, fdy, speed, planet))


def detect_threats(my_planets, enemy_fleets, step=None, orbit_table=None, eta_cache=None):
    threats = {}
    for fleet in enemy_fleets:
        for planet in my_planets:
            if fleet_hit_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache) is not None:
                threats[planet["id"]] = threats.get(planet["id"], 0) + fleet["ships"]
    return threats


def detect_reinforcements(my_planets, my_fleets, step=None, orbit_table=None, eta_cache=None):
    reinforcements = {}
    for fleet in my_fleets:
        for planet in my_planets:
            if fleet_hit_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache) is not None:
                reinforcements[planet["id"]] = reinforcements.get(planet["id"], 0) + fleet["ships"]
    return reinforcements


def detect_threats_detailed(my_planets, enemy_fleets, step=None, orbit_table=None, eta_cache=None):
    details = {}
    for fleet in enemy_fleets:
        for planet in my_planets:
            eta = fleet_hit_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache)
            if eta is not None:
                if planet["id"] not in details:
                    details[planet["id"]] = []
                details[planet["id"]].append((fleet["ships"], eta))
    return details


def detect_reinforcements_detailed(my_planets, my_fleets, step=None, orbit_table=None, eta_cache=None):
    details = {}
    for fleet in my_fleets:
        for planet in my_planets:
            eta = fleet_hit_eta(fleet, planet, step, orbit_table, eta_cache=eta_cache)
            if eta is not None:
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
