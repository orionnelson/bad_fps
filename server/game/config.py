"""Tickrates, caps, maps, weapon stats."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WeaponSpec:
    weaponId: str
    family: str  # hitscan | projectile
    damage: float
    fireRate: float  # shots/sec
    spreadRad: float
    pellets: int = 1
    range: float = 100.0
    maxAmmo: int = 30
    reloadSec: float = 2.0
    projectileSpeed: float = 0.0
    projectileRadius: float = 0.25
    explosionRadius: float = 0.0


@dataclass(frozen=True)
class MovementCaps:
    accel: float = 45.0
    maxSpeedWalk: float = 6.0
    maxSpeedSprint: float = 9.0
    friction: float = 14.0
    gravity: float = 22.0
    jumpSpeed: float = 8.5
    airControl: float = 0.35
    maxStep: float = 0.35


@dataclass
class ServerConfig:
    # Versions
    server_version: str = "0.1.0"
    protocol_version: int = 1

    # Network
    host: str = "0.0.0.0"
    port: int = 8765
    cors_allow_all: bool = True
    cors_allowed_origins: list[str] = field(default_factory=list)

    # Tick
    simulation_hz: int = 60
    # Client camera follow feels much better with >= 20 Hz snapshots.
    snapshot_hz: int = 30

    # Rooms
    max_rooms: int = 20
    max_players_per_room: int = 16
    default_map_id: str = "map01"
    kills_to_win: int = 25
    round_time_sec: float = 8 * 60.0
    respawn_sec: float = 3.0

    # Anti-cheat / validation
    max_input_buffer: int = 120
    input_seq_window: int = 240
    max_dt: float = 0.05
    max_turn_rate_rad_per_sec: float = 20.0

    # World
    player_radius: float = 0.35
    player_height: float = 1.75
    eye_height: float = 1.55

    movement: MovementCaps = field(default_factory=MovementCaps)

    # Bots
    bots_enabled: bool = True
    bot_count: int = 4

    # Persistence
    sqlite_enabled: bool = True
    sqlite_path: str = "server_stats.sqlite3"

    # Weapon specs
    weapons: dict[str, WeaponSpec] = field(default_factory=dict)

    def __post_init__(self):
        if not self.weapons:
            # Reasonable defaults if constants.json isn't loaded.
            self.weapons = {
                "pistol": WeaponSpec(
                    weaponId="pistol",
                    family="hitscan",
                    damage=18.0,
                    fireRate=3.0,
                    spreadRad=0.01,
                    range=80.0,
                    maxAmmo=12,
                    reloadSec=1.4,
                ),
                "shotgun": WeaponSpec(
                    weaponId="shotgun",
                    family="hitscan",
                    damage=8.0,
                    fireRate=1.0,
                    spreadRad=0.10,
                    pellets=8,
                    range=35.0,
                    maxAmmo=8,
                    reloadSec=2.6,
                ),
                "rocket": WeaponSpec(
                    weaponId="rocket",
                    family="projectile",
                    damage=95.0,
                    fireRate=0.8,
                    spreadRad=0.0,
                    range=120.0,
                    maxAmmo=4,
                    reloadSec=3.2,
                    projectileSpeed=22.0,
                    projectileRadius=0.18,
                    explosionRadius=3.0,
                ),
            }

    def weapon(self, weapon_id: str) -> WeaponSpec:
        return self.weapons.get(weapon_id, self.weapons["pistol"])

    @staticmethod
    def _parse_bool(v: str | None, default: bool) -> bool:
        if v is None:
            return default
        return v.strip().lower() in ("1", "true", "yes", "on")

    @classmethod
    def from_env(cls) -> "ServerConfig":
        cfg = cls()
        cfg.host = os.environ.get("FPS_HOST", cfg.host)
        cfg.port = int(os.environ.get("FPS_PORT", str(cfg.port)))
        cfg.cors_allow_all = cls._parse_bool(os.environ.get("FPS_CORS_ALLOW_ALL"), cfg.cors_allow_all)
        cfg.sqlite_enabled = cls._parse_bool(os.environ.get("FPS_SQLITE"), cfg.sqlite_enabled)
        cfg.bots_enabled = cls._parse_bool(os.environ.get("FPS_BOTS"), cfg.bots_enabled)
        if os.environ.get("FPS_BOT_COUNT"):
            try:
                cfg.bot_count = int(os.environ.get("FPS_BOT_COUNT"))
            except Exception:
                pass
        origins = os.environ.get("FPS_CORS_ORIGINS")
        if origins:
            cfg.cors_allowed_origins = [o.strip() for o in origins.split(",") if o.strip()]

        # Load shared constants if present.
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        constants_path = os.path.join(repo_root, "shared", "constants.json")
        if os.path.exists(constants_path):
            try:
                with open(constants_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                weapons = {}
                for w in data.get("weapons", []):
                    weapons[w["weaponId"]] = WeaponSpec(**w)
                if weapons:
                    cfg.weapons = weapons
                if "simulationHz" in data:
                    cfg.simulation_hz = int(data["simulationHz"])
                if "snapshotHz" in data:
                    cfg.snapshot_hz = int(data["snapshotHz"])
                if "defaultMapId" in data:
                    cfg.default_map_id = str(data["defaultMapId"])
            except Exception:
                pass

        return cfg
