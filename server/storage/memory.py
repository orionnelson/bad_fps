"""In-memory runtime state."""

from __future__ import annotations

import time


class MemoryStore:
    def __init__(self):
        self._stats: dict[str, dict] = {}

    def upsert_player(self, name: str, kills: int, deaths: int, score: int) -> None:
        cur = self._stats.get(name) or {"name": name, "kills": 0, "deaths": 0, "score": 0, "updatedAt": 0.0}
        cur["kills"] = int(kills)
        cur["deaths"] = int(deaths)
        cur["score"] = int(score)
        cur["updatedAt"] = time.time()
        self._stats[name] = cur

    def get_leaderboard(self, limit: int = 25):
        vals = list(self._stats.values())
        vals.sort(key=lambda r: (r.get("score", 0), r.get("kills", 0)), reverse=True)
        return vals[: int(limit)]
