"""Fire rate, recoil (server-side), ammo, reload."""

from __future__ import annotations

import math
import random

from server.game.systems.collision import first_obstacle_hit, ray_sphere
from server.game.systems.damage import apply_damage
from server.game.systems.projectiles import spawn_rocket
from server.game.world import v3_add, v3_dot, v3_mul, v3_norm


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _dir_from_yaw_pitch(yaw: float, pitch: float) -> list[float]:
    sy = math.sin(yaw)
    cy = math.cos(yaw)
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    # Convention: pitch > 0 means looking down.
    # Convention: yaw=0 faces -Z; positive yaw rotates LEFT (matches Three.js).
    return v3_norm([-sy * cp, -sp, -cy * cp])


def _apply_spread(base_dir: list[float], spread_rad: float, rng: random.Random) -> list[float]:
    if spread_rad <= 0.0:
        return base_dir
    # Uniform cone sample around base_dir.
    up = [0.0, 1.0, 0.0] if abs(base_dir[1]) < 0.95 else [1.0, 0.0, 0.0]
    u = v3_norm(_cross(up, base_dir))
    v = v3_norm(_cross(base_dir, u))

    theta = 2.0 * math.pi * rng.random()
    cos_max = math.cos(spread_rad)
    cos_a = 1.0 - rng.random() * (1.0 - cos_max)
    sin_a = (max(0.0, 1.0 - cos_a * cos_a)) ** 0.5

    tangent = [
        u[0] * math.cos(theta) + v[0] * math.sin(theta),
        u[1] * math.cos(theta) + v[1] * math.sin(theta),
        u[2] * math.cos(theta) + v[2] * math.sin(theta),
    ]
    d = [
        base_dir[0] * cos_a + tangent[0] * sin_a,
        base_dir[1] * cos_a + tangent[1] * sin_a,
        base_dir[2] * cos_a + tangent[2] * sin_a,
    ]
    return v3_norm(d)


def _hitscan(room, shooter_id: str, origin: list[float], direction: list[float], weapon_id: str) -> None:
    spec = room.config.weapon(weapon_id)

    # Obstacle distance.
    t_wall = first_obstacle_hit(origin, direction, room.map.colliders, spec.range)
    max_t = spec.range if t_wall is None else t_wall

    # Player hit (body sphere + head sphere).
    best_t = None
    best_pid = None
    best_head = False
    for pid, p in room.players.items():
        if pid == shooter_id or not p.alive:
            continue

        body_center = [p.pos[0], p.pos[1] + 0.9, p.pos[2]]
        head_center = [p.pos[0], p.pos[1] + 1.55, p.pos[2]]
        body_t = ray_sphere(origin, direction, body_center, room.config.player_radius)
        head_t = ray_sphere(origin, direction, head_center, room.config.player_radius * 0.55)

        t = None
        head = False
        if head_t is not None:
            t = head_t
            head = True
        if body_t is not None and (t is None or body_t < t):
            t = body_t
            head = False

        if t is None or t > max_t:
            continue

        if best_t is None or t < best_t:
            best_t = t
            best_pid = pid
            best_head = head

    if best_pid is not None:
        hit_pos = [origin[0] + direction[0] * best_t, origin[1] + direction[1] * best_t, origin[2] + direction[2] * best_t]
        apply_damage(room, shooter_id, best_pid, spec.damage, headshot=best_head, hit_pos=hit_pos)
        room._push_event("hit", {"attackerId": shooter_id, "victimId": best_pid, "weaponId": weapon_id, "headshot": best_head})
    else:
        room._push_event("miss", {"attackerId": shooter_id, "weaponId": weapon_id})


def step_weapons(room, dt: float) -> None:
    cfg = room.config

    for p in room.players.values():
        if not p.alive:
            continue

        cmd = p.lastCmd or {}
        want_weapon = str(cmd.get("weaponId", p.weaponId))
        if want_weapon in cfg.weapons:
            p.weaponId = want_weapon

        spec = cfg.weapon(p.weaponId)

        # Finish reload.
        if p.reloadingUntil and room.t >= p.reloadingUntil:
            p.ammo[p.weaponId] = spec.maxAmmo
            p.reloadingUntil = 0.0
            room.queue_event_for(p.playerId, {"type": "reload_done", "payload": {"weaponId": p.weaponId}})

        if bool(cmd.get("reload", False)) and not p.reloadingUntil:
            if p.ammo.get(p.weaponId, 0) < spec.maxAmmo:
                p.reloadingUntil = room.t + spec.reloadSec
                room.queue_event_for(p.playerId, {"type": "reload", "payload": {"weaponId": p.weaponId}})
            continue

        if p.reloadingUntil:
            continue

        fire = bool(cmd.get("fire", False))
        if not fire:
            continue

        ammo = int(p.ammo.get(p.weaponId, 0))
        if ammo <= 0:
            continue

        # Fire rate gate.
        delay = 1.0 / max(0.1, spec.fireRate)
        if (room.t - p.lastFireAt) < delay:
            continue

        # Consume ammo and fire.
        p.lastFireAt = room.t
        p.ammo[p.weaponId] = ammo - 1

        # Deterministic spread.
        seed = (room.seed ^ (hash(p.playerId) & 0xFFFFFFFF) ^ (room.server_tick * 2654435761)) & 0xFFFFFFFF
        rng = random.Random(seed)
        base_dir = _dir_from_yaw_pitch(p.yaw, p.pitch)
        origin = [p.pos[0], p.pos[1] + cfg.eye_height, p.pos[2]]

        if spec.family == "hitscan":
            for _ in range(int(spec.pellets)):
                d = _apply_spread(base_dir, spec.spreadRad, rng)
                _hitscan(room, p.playerId, origin, d, p.weaponId)
        else:
            d = base_dir
            spawn_rocket(room, p.playerId, origin, d, p.weaponId)

        room.queue_event_for(p.playerId, {"type": "fire", "payload": {"weaponId": p.weaponId}})
