"""Server-side bot behavior (utility-lite)."""

from __future__ import annotations

import math
import random

from server.game.systems.collision import first_obstacle_hit


def step_bots(room, dt: float) -> None:
    # Very simple: move toward nearest non-self, shoot if line-of-sight.
    for bot_id in list(room.bots):
        bot = room.players.get(bot_id)
        if not bot:
            continue
        if not bot.alive:
            if bot.respawnAt and room.t >= bot.respawnAt:
                room.respawn_player(bot_id)
            continue

        # Track stuckness.
        st = room.bot_state.setdefault(bot_id, {"last": [bot.pos[0], bot.pos[2]], "stuck": 0.0, "wander": None, "wanderUntil": 0.0})
        moved = math.hypot(bot.pos[0] - st["last"][0], bot.pos[2] - st["last"][1])
        st["last"] = [bot.pos[0], bot.pos[2]]
        if moved < 0.02:
            st["stuck"] += dt
        else:
            st["stuck"] = 0.0

        # Prefer targeting humans; if none, target bots.
        target = None
        best2 = None
        for pid, p in room.players.items():
            if pid == bot_id or not p.alive:
                continue
            if pid.startswith("bot_"):
                continue
            d0 = p.pos[0] - bot.pos[0]
            d2 = p.pos[2] - bot.pos[2]
            dist2 = d0 * d0 + d2 * d2
            if best2 is None or dist2 < best2:
                best2 = dist2
                target = p

        if not target:
            for pid, p in room.players.items():
                if pid == bot_id or not p.alive:
                    continue
                d0 = p.pos[0] - bot.pos[0]
                d2 = p.pos[2] - bot.pos[2]
                dist2 = d0 * d0 + d2 * d2
                if best2 is None or dist2 < best2:
                    best2 = dist2
                    target = p

        if not target:
            bot.lastCmd["moveX"] = 0.0
            bot.lastCmd["moveY"] = 0.0
            bot.lastCmd["fire"] = False
            continue

        # Wander/unstuck: if stuck for >1s, pick a random nearby reachable point.
        if st["stuck"] > 1.0 and room.t >= float(st.get("wanderUntil", 0.0)):
            rng = random.Random((room.seed ^ (hash(bot_id) & 0xFFFFFFFF) ^ int(room.t * 10)) & 0xFFFFFFFF)
            for _ in range(8):
                ang = rng.random() * math.tau
                rad = 4.0 + rng.random() * 8.0
                tx = bot.pos[0] + math.cos(ang) * rad
                tz = bot.pos[2] + math.sin(ang) * rad
                # Ensure the nav grid has a path-ish direction.
                dx0, dz0 = room.nav.next_direction(bot.pos, [tx, bot.pos[1], tz])
                if (dx0 * dx0 + dz0 * dz0) > 0.01:
                    st["wander"] = [tx, tz]
                    st["wanderUntil"] = room.t + 1.6
                    st["stuck"] = 0.0
                    break

        goal_pos = target.pos
        if st.get("wander") is not None and room.t < float(st.get("wanderUntil", 0.0)):
            goal_pos = [float(st["wander"][0]), bot.pos[1], float(st["wander"][1])]
        else:
            st["wander"] = None

        dx, dz = room.nav.next_direction(bot.pos, goal_pos)
        # Convention: yaw=0 faces -Z; positive yaw rotates LEFT.
        yaw = math.atan2(-dx, -dz)
        bot.lastCmd["yaw"] = yaw
        bot.lastCmd["pitch"] = 0.0
        bot.lastCmd["sprint"] = True
        bot.lastCmd["jump"] = False

        # Use forward movement only.
        bot.lastCmd["moveX"] = 0.0
        bot.lastCmd["moveY"] = 1.0

        # Fire if in range and line-of-sight (skip while wandering).
        spec = room.config.weapon(bot.weaponId)
        dist = 0.0 if best2 is None else (best2 ** 0.5)
        fire = False
        if st.get("wander") is None and dist <= min(28.0, spec.range):
            origin = [bot.pos[0], bot.pos[1] + room.config.eye_height, bot.pos[2]]
            direction = [dx, 0.0, dz]
            # If any wall is closer than target, don't shoot.
            t_wall = first_obstacle_hit(origin, direction, room.map.colliders, spec.range)
            if t_wall is None or t_wall >= dist:
                fire = True

        bot.lastCmd["fire"] = fire
        bot.lastCmd["weaponId"] = "pistol"
