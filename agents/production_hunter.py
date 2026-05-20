import math

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_RADIUS = 10.0


def parse_planet(planet):
    return {
        "id": planet[0],
        "owner": planet[1],
        "x": planet[2],
        "y": planet[3],
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


def target_score(src, target, player, step):
    if path_hits_sun(src, target):
        return -10**9

    distance = dist(src, target)
    is_enemy = target["owner"] not in (-1, player)
    is_neutral = target["owner"] == -1
    production = target["production"]

    production_value = production * (58 if production >= 3 else 30)
    owner_bonus = 24 if is_enemy else 9 if is_neutral else 0
    pressure_bonus = min(18, step / 20) if is_enemy else 0
    distance_penalty = distance * (1.55 if production >= 3 else 2.0)
    ship_penalty = target["ships"] * (1.05 if production >= 3 else 1.35)

    return production_value + owner_bonus + pressure_bonus - distance_penalty - ship_penalty


def ships_to_send(src, target, player):
    reserve = max(4, int(src["production"] * 2.2))
    available = int(src["ships"] - reserve)

    if available <= 0:
        return 0

    is_enemy = target["owner"] not in (-1, player)
    needed = int(target["ships"] + 2)

    if target["production"] >= 3:
        needed += int(target["production"] * 2)

    if is_enemy:
        needed += 3

    return min(available, needed)


def agent(obs):
    player = obs.get("player", 0)
    step = obs.get("step", 0)
    planets = [parse_planet(planet) for planet in obs.get("planets", [])]

    my_planets = [planet for planet in planets if planet["owner"] == player]
    targets = [planet for planet in planets if planet["owner"] != player]

    moves = []

    for src in my_planets:
        if src["ships"] < 11 or not targets:
            continue

        target = max(
            targets,
            key=lambda candidate: target_score(src, candidate, player, step),
        )
        score = target_score(src, target, player, step)

        if score < 0:
            continue

        send = ships_to_send(src, target, player)
        if send <= target["ships"]:
            continue

        angle = math.atan2(target["y"] - src["y"], target["x"] - src["x"])
        moves.append([src["id"], angle, send])

    return moves
