import math

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_RADIUS = 10.0


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


def path_hits_sun(src, dst):
    d = segment_point_distance(
        CENTER_X,
        CENTER_Y,
        src["x"],
        src["y"],
        dst["x"],
        dst["y"],
    )
    return d <= SUN_RADIUS + 0.5


def parse_planet(p):
    return {
        "id": p[0],
        "owner": p[1],
        "x": p[2],
        "y": p[3],
        "radius": p[4],
        "ships": p[5],
        "production": p[6],
    }


def target_score(src, target, player):
    d = dist(src, target)

    if path_hits_sun(src, target):
        return -10**9

    capture_cost = target["ships"] + 1

    # Neutral almak genelde expansion; enemy almak tempo swing.
    owner_bonus = 0
    if target["owner"] == -1:
        owner_bonus = 8
    elif target["owner"] != player:
        owner_bonus = 16

    production_value = target["production"] * 35
    distance_penalty = d * 2.2
    ship_penalty = capture_cost * 1.4

    return production_value + owner_bonus - distance_penalty - ship_penalty


def agent(obs):
    player = obs.get("player", 0)
    planets = [parse_planet(p) for p in obs.get("planets", [])]

    my_planets = [p for p in planets if p["owner"] == player]
    targets = [p for p in planets if p["owner"] != player]

    moves = []

    if not my_planets or not targets:
        return moves

    for src in my_planets:
        if src["ships"] < 12:
            continue

        ranked = sorted(
            targets,
            key=lambda t: target_score(src, t, player),
            reverse=True,
        )

        if not ranked:
            continue

        target = ranked[0]
        score = target_score(src, target, player)

        if score < 0:
            continue

        ships_needed = int(target["ships"] + 2)

        # Savunma bırak.
        reserve = max(5, int(src["production"] * 3))
        available = int(src["ships"] - reserve)

        if available <= 0:
            continue

        send = min(available, ships_needed)

        if send <= target["ships"]:
            continue

        angle = math.atan2(target["y"] - src["y"], target["x"] - src["x"])
        moves.append([src["id"], angle, send])

    return moves
