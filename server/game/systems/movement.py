"""Server-side movement sim + constraints."""

from __future__ import annotations

import math

from server.game.systems.collision import resolve_sphere_vs_aabb_xz


def _wrap_angle_rad(a: float) -> float:
    # Wrap to [-pi, pi]
    while a > math.pi:
        a -= math.tau
    while a < -math.pi:
        a += math.tau
    return a


def step_movement(room, dt: float) -> None:
    cfg = room.config
    caps = cfg.movement

    for p in room.players.values():
        if not p.alive:
            if p.respawnAt and room.t >= p.respawnAt:
                room.respawn_player(p.playerId)
            continue

        cmd = p.lastCmd or {}

        p.yaw = _wrap_angle_rad(float(cmd.get("yaw", p.yaw)))
        p.pitch = max(-1.4, min(1.4, float(cmd.get("pitch", p.pitch))))

        # Keep command angles normalized too (helps server-side validation).
        if p.lastCmd is not None:
            p.lastCmd["yaw"] = p.yaw
            p.lastCmd["pitch"] = p.pitch

        move_x = float(cmd.get("moveX", 0.0))
        move_y = float(cmd.get("moveY", 0.0))
        sprint = bool(cmd.get("sprint", False))
        jump = bool(cmd.get("jump", False))

        # Wish direction in world XZ.
        # Convention: yaw=0 faces -Z; positive yaw rotates LEFT (matches Three.js).
        sy = math.sin(p.yaw)
        cy = math.cos(p.yaw)
        fwd = (-sy, -cy)
        right = (cy, -sy)
        wish_x = right[0] * move_x + fwd[0] * move_y
        wish_z = right[1] * move_x + fwd[1] * move_y
        wish_len = (wish_x * wish_x + wish_z * wish_z) ** 0.5
        if wish_len > 1e-6:
            wish_x /= wish_len
            wish_z /= wish_len
        else:
            wish_x = 0.0
            wish_z = 0.0

        max_speed = caps.maxSpeedSprint if sprint else caps.maxSpeedWalk

        # Ground check.
        radius = cfg.player_radius
        on_ground = p.pos[1] <= radius + 1e-3
        if on_ground:
            p.pos[1] = radius
            if p.vel[1] < 0.0:
                p.vel[1] = 0.0

        # Friction
        if on_ground:
            vx, vz = p.vel[0], p.vel[2]
            sp = (vx * vx + vz * vz) ** 0.5
            if sp > 1e-6:
                drop = sp * caps.friction * dt
                ns = max(0.0, sp - drop)
                scale = ns / sp
                p.vel[0] *= scale
                p.vel[2] *= scale

        # Acceleration
        accel = caps.accel * (1.0 if on_ground else caps.airControl)
        p.vel[0] += wish_x * accel * dt
        p.vel[2] += wish_z * accel * dt

        # Clamp XZ speed
        vx, vz = p.vel[0], p.vel[2]
        sp = (vx * vx + vz * vz) ** 0.5
        if sp > max_speed:
            s = max_speed / sp
            p.vel[0] *= s
            p.vel[2] *= s

        # Jump
        if jump and on_ground:
            p.vel[1] = caps.jumpSpeed
            on_ground = False

        # Gravity
        p.vel[1] -= caps.gravity * dt

        # Integrate
        p.pos[0] += p.vel[0] * dt
        p.pos[1] += p.vel[1] * dt
        p.pos[2] += p.vel[2] * dt

        # Floor
        if p.pos[1] < radius:
            p.pos[1] = radius
            if p.vel[1] < 0.0:
                p.vel[1] = 0.0
            on_ground = True

        # Obstacles
        collided = False
        for a in room.map.colliders:
            p.pos, hit = resolve_sphere_vs_aabb_xz(p.pos, radius, a)
            collided = collided or hit
        if collided:
            # If we hit something, damp XZ a bit to avoid jitter.
            p.vel[0] *= 0.75
            p.vel[2] *= 0.75

        p.onGround = on_ground
