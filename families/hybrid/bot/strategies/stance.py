"""Detect the current game stance and return the ordered tactic list."""
from bot.state import MID_END

OPENING = "opening"
EXPANDING = "expanding"
FRONTLINE = "frontline"
AHEAD_CRUSHING = "ahead_crushing"
BEHIND_DESPERATE = "behind_desperate"
UNDER_SIEGE = "under_siege"


def detect_stance(step, my_planets, targets, threats_det, my_prod, enemy_prod):
    """Determine the current game stance."""
    neutrals = [t for t in targets if t["owner"] == -1]
    n_neutrals = len(neutrals)
    n_my = len(my_planets)
    n_threatened = sum(1 for p in my_planets if threats_det.get(p["id"]))

    # How many of my planets are under active threat?
    if n_threatened >= 2 and n_threatened >= n_my * 0.4:
        return UNDER_SIEGE

    if step < 60 and n_neutrals >= 3:
        return OPENING

    if enemy_prod > 0 and my_prod < enemy_prod * 0.7:
        return BEHIND_DESPERATE

    if enemy_prod > 0 and my_prod > enemy_prod * 1.5:
        return AHEAD_CRUSHING

    if n_neutrals >= 2:
        return EXPANDING

    return FRONTLINE


def get_tactic_order(stance):
    """Return ordered list of tactic names for the given stance."""
    if stance == OPENING:
        return ["comet_rush", "chain_expand", "snipe", "core_attack", "overflow"]

    if stance == EXPANDING:
        return ["snipe", "chain_expand", "comet_rush", "reinforce", "core_attack", "overflow"]

    if stance == FRONTLINE:
        return ["counter_punch", "prod_starve", "reinforce", "evacuation",
                "core_attack", "sync", "overflow"]

    if stance == AHEAD_CRUSHING:
        return ["sync", "vulture", "counter_punch", "honeypot",
                "core_attack", "overflow"]

    if stance == BEHIND_DESPERATE:
        return ["evacuation", "turtle", "vulture", "counter_punch", "core_attack"]

    if stance == UNDER_SIEGE:
        return ["evacuation", "reinforce", "turtle", "core_attack"]

    return ["core_attack"]
