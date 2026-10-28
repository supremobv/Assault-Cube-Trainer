"""Pure angle geometry and bot selection, independent of process memory."""
import math


def angle_delta(target, current):
    return (target-current+180.) % 360. - 180.


def angles_to(source, target):
    dx, dy, dz = (b-a for a, b in zip(source, target))
    flat = math.hypot(dx, dy)
    if flat < 1e-6:
        return None
    return math.degrees(math.atan2(dx, -dy)) % 360., math.degrees(math.atan2(dz, flat))


def choose_target(bots, source, yaw, pitch, team, *, head=False, cone=35., max_distance=250., team_filter=True, rendered_only=True, preferred=None, nearest=False):
    choices = []
    for bot in bots:
        if bot['type'] not in (0,1) or bot['state'] != 0 or bot['health'] <= 0:
            continue
        if team_filter and bot['team'] == team:
            continue
        if rendered_only and not bot['rendered']:
            continue
        if head:
            if not bot['head_valid']:
                continue
            target = bot['head']
        else:
            x, y, z = bot['position']
            target = (x, y, z-bot['eye_height']*.45)
        distance = math.dist(source, target)
        if distance < .5 or distance > max_distance:
            continue
        angles = angles_to(source, target)
        if angles is None:
            continue
        dyaw, dpitch = angle_delta(angles[0], yaw), angles[1]-pitch
        error = math.hypot(dyaw, dpitch)
        if error <= cone:
            choices.append(dict(bot, aim_angles=angles, error=error, distance=distance))
    if preferred is not None:
        locked = next((item for item in choices if item['pointer'] == preferred), None)
        if locked:
            return locked
    rank = (lambda item: (item['distance'], item['error'])) if nearest else (lambda item: (item['error'], item['distance']))
    return min(choices, key=rank) if choices else None
