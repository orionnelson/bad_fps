"""Hitscan + projectile updates."""

from __future__ import annotations

import math
import uuid

from server.game.systems.collision import first_obstacle_hit, ray_sphere, sphere_intersects_aabb
from server.game.systems.damage import apply_damage
from server.game.world import v3_add, v3_dot, v3_mul, v3_sub, v3_len, v3_norm


def spawn_rocket(room, owner_id: str, origin: list[float], direction: list[float], weapon_id: str) -> None:
    spec = room.config.weapon(weapon_id)
    pid = uuid.uuid4().hex[:10]
    from server.game.room import Projectile

    room.projectiles[pid] = Projectile(
        projectileId=pid,
        ownerId=owner_id,
        weaponId=weapon_id,
        pos=[origin[0], origin[1], origin[2]],
        vel=[direction[0] * spec.projectileSpeed, direction[1] * spec.projectileSpeed, direction[2] * spec.projectileSpeed],
        radius=spec.projectileRadius,
        ttl=4.0,
    )
    room._push_event("projectile_spawn", {"projectileId": pid, "ownerId": owner_id, "weaponId": weapon_id})


def _explode(room, owner_id: str, pos: list[float], weapon_id: str) -> None:
    spec = room.config.weapon(weapon_id)
    r = float(spec.explosionRadius or 0.0)
    if r <= 0.0:
        return
    room._push_event("explosion", {"pos": pos, "radius": r, "weaponId": weapon_id})

    for pid, p in room.players.items():
        if not p.alive:
            continue
        d = v3_sub(p.pos, pos)
        d[1] = 0.0
        dist = v3_len(d)
        if dist > r:
            continue
        falloff = max(0.0, 1.0 - (dist / r))
        dmg = spec.damage * falloff
        if dmg <= 0.5:
            continue
        apply_damage(room, owner_id, pid, dmg, headshot=False, hit_pos=pos)


def step_projectiles(room, dt: float) -> None:
    to_delete = []
    for pid, pr in room.projectiles.items():
        pr.ttl -= dt
        if pr.ttl <= 0.0:
            to_delete.append(pid)
            continue

        # Integrate.
        pr.vel[1] -= 3.0 * dt
        pr.pos[0] += pr.vel[0] * dt
        pr.pos[1] += pr.vel[1] * dt
        pr.pos[2] += pr.vel[2] * dt

        # Collide with obstacles.
        hit = False
        for a in room.map.colliders:
            if sphere_intersects_aabb(pr.pos, pr.radius, a):
                hit = True
                break

        # Collide with players.
        if not hit:
            for pid2, p in room.players.items():
                if not p.alive or pid2 == pr.ownerId:
                    continue
                d = v3_sub(p.pos, pr.pos)
                d[1] = 0.0
                if v3_dot(d, d) <= (room.config.player_radius + pr.radius) ** 2:
                    hit = True
                    break

        if hit:
            _explode(room, pr.ownerId, pr.pos, pr.weaponId)
            room._push_event("projectile_hit", {"projectileId": pr.projectileId, "pos": pr.pos, "weaponId": pr.weaponId})
            to_delete.append(pid)

    for pid in to_delete:
        room.projectiles.pop(pid, None)
