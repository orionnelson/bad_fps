"""SQLite persistence for stats/leaderboard."""

from __future__ import annotations

import sqlite3
import time


class SqliteStore:
    def __init__(self, path: str):
        self.path = path
        self.conn: sqlite3.Connection | None = None

    def init(self) -> None:
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_stats (
              name TEXT PRIMARY KEY,
              kills INTEGER NOT NULL,
              deaths INTEGER NOT NULL,
              score INTEGER NOT NULL,
              updated_at REAL NOT NULL
            )
            """
        )
        self.conn.commit()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def upsert_player(self, name: str, kills: int, deaths: int, score: int) -> None:
        if not self.conn:
            return
        self.conn.execute(
            """
            INSERT INTO player_stats (name, kills, deaths, score, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
              kills=excluded.kills,
              deaths=excluded.deaths,
              score=excluded.score,
              updated_at=excluded.updated_at
            """,
            (name, int(kills), int(deaths), int(score), time.time()),
        )
        self.conn.commit()

    def get_leaderboard(self, limit: int = 25):
        if not self.conn:
            return []
        cur = self.conn.execute(
            "SELECT name, kills, deaths, score, updated_at FROM player_stats ORDER BY score DESC, kills DESC LIMIT ?",
            (int(limit),),
        )
        out = []
        for row in cur.fetchall():
            out.append({"name": row[0], "kills": row[1], "deaths": row[2], "score": row[3], "updatedAt": row[4]})
        return out
