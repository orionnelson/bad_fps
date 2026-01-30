"""Snapshot cache + (light) delta compression."""

from __future__ import annotations

from typing import Any


def _diff_fields(prev: dict[str, Any], cur: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    out = {}
    for f in fields:
        if prev.get(f) != cur.get(f):
            out[f] = cur.get(f)
    return out


class SnapshotCache:
    def __init__(self):
        self._last_by_player: dict[str, dict[str, Any]] = {}

    def clear(self, player_id: str) -> None:
        self._last_by_player.pop(player_id, None)

    def make(self, player_id: str, server_tick: int, snapshot: dict[str, Any], want_delta: bool) -> dict[str, Any]:
        cur = {
            "serverTick": server_tick,
            **snapshot,
        }
        if not want_delta:
            self._last_by_player[player_id] = cur
            return {"mode": "full", **cur}

        prev = self._last_by_player.get(player_id)
        if not prev:
            self._last_by_player[player_id] = cur
            return {"mode": "full", **cur}

        delta = {
            "serverTick": server_tick,
            "baseTick": prev.get("serverTick"),
            "you": _diff_fields(prev.get("you", {}), cur.get("you", {}), [
                "pos",
                "vel",
                "yaw",
                "pitch",
                "hp",
                "armor",
                "ammo",
                "weaponId",
                "alive",
                "kills",
                "deaths",
                "score",
                "lastSeq",
            ]),
            "others": cur.get("others", []),
            "projectiles": cur.get("projectiles", []),
            "pickups": cur.get("pickups", []),
            "events": cur.get("events", []),
        }
        # Note: delta for others/projectiles/pickups is full lists for simplicity.
        self._last_by_player[player_id] = cur
        return {"mode": "delta", **delta}
