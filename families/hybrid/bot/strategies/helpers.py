"""Shared helper functions for all tactics."""
from bot.geometry import dist_xy, path_hits_sun


def available_ships(src, threats, P):
    """How many ships a planet can spare for offense."""
    threat = threats.get(src["id"], 0)
    reserve = max(P["min_reserve"], int(src["production"] * P["reserve_prod_mult"])) + threat
    return max(0, int(src["ships"] - reserve))


def can_reach(src_x, src_y, tx, ty):
    """Check path is not blocked by sun."""
    return not path_hits_sun(src_x, src_y, tx, ty)
