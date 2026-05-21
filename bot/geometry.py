import math

CENTER_X = 50.0
CENTER_Y = 50.0
SUN_RADIUS = 10.0
MAX_FLEET_SPEED = 6.0

def dist_xy(x1, y1, x2, y2):
    return math.hypot(x1 - x2, y1 - y2)

def segment_point_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def path_hits_sun(sx, sy, tx, ty):
    return segment_point_distance(CENTER_X, CENTER_Y, sx, sy, tx, ty) <= SUN_RADIUS + 0.5

def fleet_speed(ships):
    if ships <= 1:
        return 1.0
    return min(MAX_FLEET_SPEED, 1.0 + 5.0 * (math.log(ships) / math.log(1000)) ** 1.5)

def travel_time(distance, ships):
    return distance / fleet_speed(ships) if ships > 0 else 999.0

def predict_pos(pid, at_step, orbit_table):
    info = orbit_table.get(pid)
    if not info:
        return None
    angle = info["a0"] + info["av"] * at_step
    return (CENTER_X + info["r"] * math.cos(angle),
            CENTER_Y + info["r"] * math.sin(angle))

def aim_angle(src, target, send_ships, step, orbit_table):
    tx, ty = target["x"], target["y"]
    if target["id"] in orbit_table:
        for _ in range(2):
            d = dist_xy(src["x"], src["y"], tx, ty)
            tt = travel_time(d, send_ships)
            pred = predict_pos(target["id"], step + tt, orbit_table)
            if pred:
                tx, ty = pred
        if path_hits_sun(src["x"], src["y"], tx, ty):
            tx, ty = target["x"], target["y"]
    return math.atan2(ty - src["y"], tx - src["x"])
