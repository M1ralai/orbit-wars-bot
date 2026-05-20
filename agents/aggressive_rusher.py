import math


def agent(obs):
    player = obs.get("player", 0)
    planets = obs.get("planets", [])

    my_planets = [p for p in planets if p[1] == player]
    enemy_planets = [p for p in planets if p[1] not in (-1, player)]
    neutral_planets = [p for p in planets if p[1] == -1]

    moves = []

    for src in my_planets:
        if src[5] < 15:
            continue

        targets = enemy_planets or neutral_planets
        if not targets:
            continue

        target = min(
            targets,
            key=lambda t: math.hypot(src[2] - t[2], src[3] - t[3]),
        )

        send = int(src[5] * 0.75)

        if send <= target[5]:
            continue

        angle = math.atan2(target[3] - src[3], target[2] - src[2])
        moves.append([src[0], angle, send])

    return moves
