"""Armor/headshot multipliers, knockback."""

from __future__ import annotations

import math

from server.game.world import v3_add, v3_mul, v3_sub, v3_norm


def apply_damage(room, attacker_id: str, victim_id: str, base_damage: float, *, headshot: bool, hit_pos: list[float] | None = None) -> None:
    attacker = room.players.get(attacker_id)
    victim = room.players.get(victim_id)
    if not attacker or not victim:
        return
    if not attacker.alive or not victim.alive:
        return

    dmg = float(base_damage) * (2.0 if headshot else 1.0)

    # Armor absorbs 50% until depleted.
    if victim.armor > 0.0:
        absorbed = min(victim.armor, dmg * 0.5)
        victim.armor -= absorbed
        dmg -= absorbed

    victim.hp -= dmg

    room.queue_event_for(
        attacker_id,
        {
            "type": "hit",
            "payload": {"attackerId": attacker_id, "victimId": victim_id, "headshot": headshot, "damage": dmg},
        },
    )
    room._push_event("damage", {"attackerId": attacker_id, "victimId": victim_id, "damage": dmg, "headshot": headshot})

    # Knockback (small) for rockets/explosions.
    if hit_pos is not None:
        d = v3_sub(victim.pos, hit_pos)
        d[1] = 0.0
        n = v3_norm(d)
        victim.vel[0] += n[0] * 1.5
        victim.vel[2] += n[2] * 1.5

    if victim.hp > 0.0:
        return

    victim.hp = 0.0
    victim.alive = False
    victim.deaths += 1
    attacker.kills += 1
    attacker.score += 100
    room._push_event("kill", {"killerId": attacker_id, "victimId": victim_id, "killer": attacker.name, "victim": victim.name})

    # Respawn timer.
    victim.respawnAt = room.t + room.config.respawn_sec

    # Persist basic stats (humans and bots both update; you can filter if desired).
    room.memory.upsert_player(attacker.name, attacker.kills, attacker.deaths, attacker.score)
    room.memory.upsert_player(victim.name, victim.kills, victim.deaths, victim.score)
    if room.sqlite:
        room.sqlite.upsert_player(attacker.name, attacker.kills, attacker.deaths, attacker.score)
        room.sqlite.upsert_player(victim.name, victim.kills, victim.deaths, victim.score)
