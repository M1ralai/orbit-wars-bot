import math

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_RADIUS = 10.0

MIN_SHIPS = 9
MIN_RESERVE = 4
RESERVE_PROD_MULT = 2.4
NEUTRAL_BONUS = 13
ENEMY_BONUS = 12
PRESSURE_MAX = 0
PRESSURE_DIVISOR = 1
PRODUCTION_WEIGHT = 38
HIGH_PRODUCTION_WEIGHT = 48
DISTANCE_WEIGHT = 1.95
HIGH_DISTANCE_WEIGHT = 1.65
SHIP_WEIGHT = 1.25
HIGH_SHIP_WEIGHT = 1.05
OVERKILL = 2
HIGH_PROD_EXTRA = 1
ENEMY_EXTRA = 0


def parse_planet(planet):
    return {
        "id": planet[0],
        "owner": planet[1],
        "x": planet[2],
        "y": planet[3],
        "radius": planet[4],
        "ships": planet[5],
        "production": planet[6],
    }


def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def segment_point_distance(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay

    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    cx = ax + t * dx
    cy = ay + t * dy

    return math.hypot(px - cx, py - cy)


def path_hits_sun(src, target):
    distance_to_sun = segment_point_distance(
        CENTER_X,
        CENTER_Y,
        src["x"],
        src["y"],
        target["x"],
        target["y"],
    )
    return distance_to_sun <= SUN_RADIUS + 0.5


def capture_cost(target, player, assigned):
    already_sent = assigned.get(target["id"], 0)
    needed = int(target["ships"] + OVERKILL - already_sent)

    if target["production"] >= 3:
        needed += int(target["production"] * HIGH_PROD_EXTRA)

    if target["owner"] not in (-1, player):
        needed += ENEMY_EXTRA

    return max(0, needed)


def target_score(src, target, player, step, assigned):
    if path_hits_sun(src, target):
        return -10**9

    needed = capture_cost(target, player, assigned)
    if needed <= 0:
        return -10**8

    distance = dist(src, target)
    high_production = target["production"] >= 3
    is_enemy = target["owner"] not in (-1, player)

    owner_bonus = NEUTRAL_BONUS if target["owner"] == -1 else ENEMY_BONUS
    pressure_bonus = min(PRESSURE_MAX, step / PRESSURE_DIVISOR) if is_enemy else 0
    production_weight = HIGH_PRODUCTION_WEIGHT if high_production else PRODUCTION_WEIGHT
    distance_weight = HIGH_DISTANCE_WEIGHT if high_production else DISTANCE_WEIGHT
    ship_weight = HIGH_SHIP_WEIGHT if high_production else SHIP_WEIGHT

    return (
        target["production"] * production_weight
        + owner_bonus
        + pressure_bonus
        - distance * distance_weight
        - needed * ship_weight
    )


def ships_to_send(src, target, player, assigned):
    reserve = max(MIN_RESERVE, int(src["production"] * RESERVE_PROD_MULT))
    available = int(src["ships"] - reserve)

    if available <= 0:
        return 0

    needed = capture_cost(target, player, assigned)
    return min(available, needed)


def agent(obs):
    player = obs.get("player", 0)
    step = obs.get("step", 0)
    planets = [parse_planet(planet) for planet in obs.get("planets", [])]

    my_planets = [planet for planet in planets if planet["owner"] == player]
    targets = [planet for planet in planets if planet["owner"] != player]

    my_planets.sort(key=lambda planet: planet["ships"], reverse=True)

    moves = []
    assigned = {}

    for src in my_planets:
        if src["ships"] < MIN_SHIPS or not targets:
            continue

        target = max(
            targets,
            key=lambda candidate: target_score(src, candidate, player, step, assigned),
        )
        score = target_score(src, target, player, step, assigned)

        if score < 0:
            continue

        send = ships_to_send(src, target, player, assigned)
        if send <= target["ships"] - assigned.get(target["id"], 0):
            continue

        angle = math.atan2(target["y"] - src["y"], target["x"] - src["x"])
        moves.append([src["id"], angle, send])
        assigned[target["id"]] = assigned.get(target["id"], 0) + send

    return moves
