"""Kills, assists, win conditions."""

from __future__ import annotations


def step_scoring(room, dt: float) -> None:
    # Round timer.
    if room._round_active and room.t >= room._round_ends_at:
        room._round_active = False
        room._push_event("round_end", {"reason": "time"})

    # Kills to win.
    if room._round_active:
        for p in room.players.values():
            if p.kills >= room.config.kills_to_win:
                room._round_active = False
                room._push_event("round_end", {"reason": "kills", "winnerId": p.playerId, "winner": p.name})
                break

    # Reset if round ended.
    if not room._round_active and room.players:
        # Give a short pause.
        if getattr(room, "_reset_at", 0.0) == 0.0:
            room._reset_at = room.t + 4.0
        if room.t >= room._reset_at:
            room._reset_at = 0.0
            room._round_active = True
            room._round_started_at = room.t
            room._round_ends_at = room.t + room.config.round_time_sec
            # reset scores
            for p in room.players.values():
                p.kills = 0
                p.deaths = 0
                p.score = 0
                if not p.alive:
                    room.respawn_player(p.playerId)
            room.projectiles.clear()
            room._push_event("round_start", {"roomId": room.room_id, "mapId": room.map_id})
