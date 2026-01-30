"""Spawn, pickup rules, cooldowns."""

from __future__ import annotations

from server.game.world import v3_dot, v3_sub


def step_powerups(room, dt: float) -> None:
    # Respawn pickups.
    for pk in room.pickups.values():
        if pk.available:
            continue
        if pk.respawnAt and room.t >= pk.respawnAt:
            pk.available = True
            pk.respawnAt = 0.0
            room._push_event("pickup_spawn", {"pickupId": pk.pickupId, "kind": pk.kind})

    # Pickup check.
    pr = room.config.player_radius
    for p in room.players.values():
        if not p.alive:
            continue
        for pk in room.pickups.values():
            if not pk.available:
                continue
            d = v3_sub(p.pos, pk.pos)
            d[1] = 0.0
            if v3_dot(d, d) > (pr + 0.45) ** 2:
                continue

            if pk.kind == "health":
                before = p.hp
                p.hp = min(100.0, p.hp + 35.0)
                if p.hp != before:
                    room.queue_event_for(p.playerId, {"type": "pickup", "payload": {"kind": "health", "amount": p.hp - before}})
            elif pk.kind == "armor":
                before = p.armor
                p.armor = min(75.0, p.armor + 25.0)
                if p.armor != before:
                    room.queue_event_for(p.playerId, {"type": "pickup", "payload": {"kind": "armor", "amount": p.armor - before}})
            elif pk.kind == "ammo":
                wid = p.weaponId
                spec = room.config.weapon(wid)
                p.ammo[wid] = min(spec.maxAmmo, int(p.ammo.get(wid, 0)) + max(1, spec.maxAmmo // 2))
                room.queue_event_for(p.playerId, {"type": "pickup", "payload": {"kind": "ammo", "weaponId": wid}})

            pk.available = False
            pk.respawnAt = room.t + 18.0
            room._push_event("pickup", {"playerId": p.playerId, "pickupId": pk.pickupId, "kind": pk.kind})
