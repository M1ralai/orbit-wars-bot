import math


def agent(obs):
    player = obs.get("player", 0)
    planets = obs.get("planets", [])

    my_planets = [p for p in planets if p[1] == player]
    targets = [p for p in planets if p[1] != player]

    moves = []

    for src in my_planets:
        if src[5] < 10 or not targets:
            continue

        target = min(
            targets,
            key=lambda t: math.hypot(src[2] - t[2], src[3] - t[3]),
        )

        send = int(min(src[5] - 5, target[5] + 2))

        if send > target[5]:
            angle = math.atan2(target[3] - src[3], target[2] - src[2])
            moves.append([src[0], angle, send])

    return moves
