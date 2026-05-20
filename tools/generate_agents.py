import argparse
import json
from pathlib import Path


TEMPLATE = '''import math

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_RADIUS = 10.0

MIN_SHIPS = {min_ships}
MIN_RESERVE = {min_reserve}
RESERVE_PROD_MULT = {reserve_prod_mult}
NEUTRAL_BONUS = {neutral_bonus}
ENEMY_BONUS = {enemy_bonus}
PRESSURE_MAX = {pressure_max}
PRESSURE_DIVISOR = {pressure_divisor}
PRODUCTION_WEIGHT = {production_weight}
HIGH_PRODUCTION_WEIGHT = {high_production_weight}
DISTANCE_WEIGHT = {distance_weight}
HIGH_DISTANCE_WEIGHT = {high_distance_weight}
SHIP_WEIGHT = {ship_weight}
HIGH_SHIP_WEIGHT = {high_ship_weight}
OVERKILL = {overkill}
HIGH_PROD_EXTRA = {high_prod_extra}
ENEMY_EXTRA = {enemy_extra}


def parse_planet(planet):
    return {{
        "id": planet[0],
        "owner": planet[1],
        "x": planet[2],
        "y": planet[3],
        "radius": planet[4],
        "ships": planet[5],
        "production": planet[6],
    }}


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
    assigned = {{}}

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
'''


CANDIDATES = {
    "gen_balanced_claim": {
        "min_ships": 12,
        "min_reserve": 5,
        "reserve_prod_mult": 3.0,
        "neutral_bonus": 8,
        "enemy_bonus": 16,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 35,
        "high_production_weight": 40,
        "distance_weight": 2.15,
        "high_distance_weight": 1.95,
        "ship_weight": 1.4,
        "high_ship_weight": 1.25,
        "overkill": 2,
        "high_prod_extra": 0,
        "enemy_extra": 0,
    },
    "gen_eco_light": {
        "min_ships": 12,
        "min_reserve": 5,
        "reserve_prod_mult": 3.0,
        "neutral_bonus": 10,
        "enemy_bonus": 14,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 36,
        "high_production_weight": 48,
        "distance_weight": 2.15,
        "high_distance_weight": 1.75,
        "ship_weight": 1.35,
        "high_ship_weight": 1.15,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 0,
    },
    "gen_eco_commit": {
        "min_ships": 11,
        "min_reserve": 4,
        "reserve_prod_mult": 2.7,
        "neutral_bonus": 12,
        "enemy_bonus": 16,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 34,
        "high_production_weight": 55,
        "distance_weight": 2.05,
        "high_distance_weight": 1.6,
        "ship_weight": 1.3,
        "high_ship_weight": 1.05,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 1,
    },
    "gen_tempo_enemy": {
        "min_ships": 12,
        "min_reserve": 5,
        "reserve_prod_mult": 2.8,
        "neutral_bonus": 8,
        "enemy_bonus": 26,
        "pressure_max": 16,
        "pressure_divisor": 24,
        "production_weight": 34,
        "high_production_weight": 44,
        "distance_weight": 2.1,
        "high_distance_weight": 1.8,
        "ship_weight": 1.3,
        "high_ship_weight": 1.1,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 3,
    },
    "gen_fast_expand": {
        "min_ships": 9,
        "min_reserve": 4,
        "reserve_prod_mult": 2.4,
        "neutral_bonus": 13,
        "enemy_bonus": 12,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 38,
        "high_production_weight": 48,
        "distance_weight": 1.95,
        "high_distance_weight": 1.65,
        "ship_weight": 1.25,
        "high_ship_weight": 1.05,
        "overkill": 2,
        "high_prod_extra": 1,
        "enemy_extra": 0,
    },
    "gen_safe_expand": {
        "min_ships": 14,
        "min_reserve": 7,
        "reserve_prod_mult": 3.7,
        "neutral_bonus": 10,
        "enemy_bonus": 14,
        "pressure_max": 0,
        "pressure_divisor": 1,
        "production_weight": 37,
        "high_production_weight": 47,
        "distance_weight": 2.0,
        "high_distance_weight": 1.7,
        "ship_weight": 1.45,
        "high_ship_weight": 1.25,
        "overkill": 2,
        "high_prod_extra": 0,
        "enemy_extra": 0,
    },
    "gen_enemy_snipe": {
        "min_ships": 13,
        "min_reserve": 5,
        "reserve_prod_mult": 3.0,
        "neutral_bonus": 6,
        "enemy_bonus": 34,
        "pressure_max": 22,
        "pressure_divisor": 18,
        "production_weight": 32,
        "high_production_weight": 43,
        "distance_weight": 2.0,
        "high_distance_weight": 1.75,
        "ship_weight": 1.2,
        "high_ship_weight": 1.05,
        "overkill": 3,
        "high_prod_extra": 1,
        "enemy_extra": 5,
    },
    "gen_low_cost": {
        "min_ships": 10,
        "min_reserve": 4,
        "reserve_prod_mult": 2.6,
        "neutral_bonus": 9,
        "enemy_bonus": 18,
        "pressure_max": 10,
        "pressure_divisor": 30,
        "production_weight": 35,
        "high_production_weight": 43,
        "distance_weight": 2.15,
        "high_distance_weight": 1.85,
        "ship_weight": 1.05,
        "high_ship_weight": 0.95,
        "overkill": 2,
        "high_prod_extra": 0,
        "enemy_extra": 1,
    },
}


def write_candidate(name, params, output_dir):
    output_path = output_dir / f"{name}.py"
    output_path.write_text(TEMPLATE.format(**params), encoding="utf-8")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("agents/generated"))
    return parser.parse_args()


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    for name, params in CANDIDATES.items():
        output_path = write_candidate(name, params, args.output_dir)
        manifest[name] = str(output_path)

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    for name, path in manifest.items():
        print(f"{name}={path}")


if __name__ == "__main__":
    main()
