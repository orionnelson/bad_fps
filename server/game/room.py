"""Room lifecycle."""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from typing import Any

from server.game.config import ServerConfig
from server.game.world import MapData, clamp, load_map, v3
from server.game.systems.movement import step_movement
from server.game.systems.weapons import step_weapons
from server.game.systems.projectiles import step_projectiles
from server.game.systems.powerups import step_powerups
from server.game.systems.scoring import step_scoring
from server.ai.behavior import step_bots


@dataclass
class Player:
    playerId: str
    name: str
    pos: list[float]
    vel: list[float]
    yaw: float
    pitch: float
    hp: float
    armor: float
    weaponId: str
    ammo: dict[str, int]
    alive: bool
    respawnAt: float
    lastInputSeq: int
    lastCmd: dict[str, Any]
    lastFireAt: float
    reloadingUntil: float
    onGround: bool

    kills: int = 0
    deaths: int = 0
    score: int = 0


@dataclass
class Projectile:
    projectileId: str
    ownerId: str
    weaponId: str
    pos: list[float]
    vel: list[float]
    radius: float
    ttl: float


@dataclass
class Pickup:
    pickupId: str
    kind: str
    pos: list[float]
    available: bool
    respawnAt: float


class Room:
    def __init__(
        self,
        room_id: str,
        map_id: str,
        config: ServerConfig,
        memory,
        sqlite,
    ):
        self.room_id = room_id
        self.map_id = map_id
        self.config = config
        self.memory = memory
        self.sqlite = sqlite

        self.map: MapData = load_map(map_id)
        self.seed = random.randint(1, 2**31 - 1)
        self.rng = random.Random(self.seed)

        self.players: dict[str, Player] = {}
        self.projectiles: dict[str, Projectile] = {}
        self.pickups: dict[str, Pickup] = {}
        self.bots: set[str] = set()
        self.bot_state: dict[str, dict[str, Any]] = {}

        self._events: list[dict[str, Any]] = []
        self._events_for: dict[str, list[dict[str, Any]]] = {}

        self.t: float = 0.0
        self.server_tick: int = 0

        self._round_started_at = 0.0
        self._round_ends_at = 0.0
        self._round_active = False

        self._init_pickups()
        self._ensure_bots()

        from server.ai.nav import GridNav

        self.nav = GridNav(self.map, cell_size=1.0, pad=self.config.player_radius)

    @property
    def player_count(self) -> int:
        return len([p for p in self.players.values() if not p.playerId.startswith("bot_")])

    def public_info(self) -> dict[str, Any]:
        return {
            "roomId": self.room_id,
            "mapId": self.map_id,
            "players": len(self.players),
            "maxPlayers": self.config.max_players_per_room,
        }

    def _init_pickups(self) -> None:
        for p in self.map.pickups:
            pid = p.get("pickupId") or uuid.uuid4().hex[:10]
            self.pickups[pid] = Pickup(
                pickupId=pid,
                kind=str(p.get("kind", "health")),
                pos=[float(p["pos"][0]), float(p["pos"][1]), float(p["pos"][2])],
                available=True,
                respawnAt=0.0,
            )

    def _ensure_bots(self) -> None:
        if not self.config.bots_enabled:
            return
        max_bots = max(0, min(int(self.config.bot_count), self.config.max_players_per_room - 1))
        while len(self.bots) < max_bots:
            bot_id = f"bot_{uuid.uuid4().hex[:8]}"
            self.bots.add(bot_id)
            self._spawn_player(bot_id, name=f"Bot {len(self.bots)}")

    def _spawn_player(self, player_id: str, name: str) -> Player:
        spawn = self.rng.choice(self.map.spawns) if self.map.spawns else v3(0.0, 0.0, 0.0)
        ammo = {wid: self.config.weapon(wid).maxAmmo for wid in self.config.weapons.keys()}
        p = Player(
            playerId=player_id,
            name=name,
            pos=[spawn[0], spawn[1], spawn[2]],
            vel=[0.0, 0.0, 0.0],
            yaw=0.0,
            pitch=0.0,
            hp=100.0,
            armor=0.0,
            weaponId="pistol",
            ammo=ammo,
            alive=True,
            respawnAt=0.0,
            lastInputSeq=-1,
            lastCmd={
                "moveX": 0.0,
                "moveY": 0.0,
                "jump": False,
                "sprint": False,
                "yaw": 0.0,
                "pitch": 0.0,
                "fire": False,
                "weaponId": "pistol",
                "reload": False,
            },
            lastFireAt=-999.0,
            reloadingUntil=0.0,
            onGround=False,
        )
        self.players[player_id] = p
        return p

    def add_player(self, player_id: str, name: str) -> Player:
        if player_id in self.players:
            return self.players[player_id]
        if len(self.players) >= self.config.max_players_per_room:
            raise ValueError("room full")
        p = self._spawn_player(player_id, name)
        self._push_event("join", {"playerId": p.playerId, "name": p.name})
        if not self._round_active:
            self._start_round()
        return p

    def remove_player(self, player_id: str) -> None:
        p = self.players.pop(player_id, None)
        if p:
            self._push_event("leave", {"playerId": p.playerId, "name": p.name})

    def _start_round(self) -> None:
        self._round_active = True
        self._round_started_at = 0.0
        self._round_ends_at = self.config.round_time_sec
        self._push_event("round_start", {"roomId": self.room_id, "mapId": self.map_id})

    def queue_event_for(self, player_id: str, event: dict[str, Any]) -> None:
        self._events_for.setdefault(player_id, []).append(event)

    def _push_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self._events.append({"type": event_type, "payload": payload})

    def apply_input(self, player_id: str, cmd: dict[str, Any]) -> None:
        p = self.players.get(player_id)
        if not p:
            return
        # Store last command; room step uses it (server fixed tick).
        p.lastCmd = cmd

    def step(self, server_tick: int, dt: float) -> None:
        self.server_tick = int(server_tick)
        self.t += float(dt)
        # bots decide intent
        step_bots(self, dt)

        # systems
        step_movement(self, dt)
        step_weapons(self, dt)
        step_projectiles(self, dt)
        step_powerups(self, dt)
        step_scoring(self, dt)

        # Keep within bounds (simple clamp)
        bmin, bmax = self.map.bounds.min, self.map.bounds.max
        for p in self.players.values():
            p.pos[0] = clamp(p.pos[0], bmin[0], bmax[0])
            p.pos[2] = clamp(p.pos[2], bmin[2], bmax[2])

    def respawn_player(self, player_id: str) -> None:
        p = self.players.get(player_id)
        if not p:
            return
        spawn = self.rng.choice(self.map.spawns) if self.map.spawns else v3(0.0, 0.0, 0.0)
        p.pos = [spawn[0], spawn[1], spawn[2]]
        p.vel = [0.0, 0.0, 0.0]
        p.hp = 100.0
        p.armor = 0.0
        p.alive = True
        p.respawnAt = 0.0
        p.reloadingUntil = 0.0
        p.onGround = False
        self._push_event("respawn", {"playerId": p.playerId})

    def _snapshot_for(self, player_id: str) -> dict[str, Any]:
        you = self.players.get(player_id)
        if not you:
            return {}

        others = []
        for pid, p in self.players.items():
            if pid == player_id:
                continue
            others.append(
                {
                    "playerId": p.playerId,
                    "name": p.name,
                    "pos": p.pos,
                    "vel": p.vel,
                    "yaw": p.yaw,
                    "pitch": p.pitch,
                    "hp": p.hp,
                    "armor": p.armor,
                    "weaponId": p.weaponId,
                    "alive": p.alive,
                    "kills": p.kills,
                    "deaths": p.deaths,
                    "score": p.score,
                }
            )

        projs = []
        for pr in self.projectiles.values():
            projs.append(
                {
                    "projectileId": pr.projectileId,
                    "ownerId": pr.ownerId,
                    "weaponId": pr.weaponId,
                    "pos": pr.pos,
                    "vel": pr.vel,
                    "radius": pr.radius,
                }
            )

        picks = []
        for pk in self.pickups.values():
            picks.append(
                {
                    "pickupId": pk.pickupId,
                    "kind": pk.kind,
                    "pos": pk.pos,
                    "available": pk.available,
                }
            )

        events = []
        events.extend(self._events)
        events.extend(self._events_for.pop(player_id, []))
        return {
            "you": {
                "playerId": you.playerId,
                "pos": you.pos,
                "vel": you.vel,
                "yaw": you.yaw,
                "pitch": you.pitch,
                "hp": you.hp,
                "armor": you.armor,
                "weaponId": you.weaponId,
                "ammo": you.ammo.get(you.weaponId, 0),
                "alive": you.alive,
                "kills": you.kills,
                "deaths": you.deaths,
                "score": you.score,
                "lastSeq": you.lastInputSeq,
                "cmd": {
                    "moveX": float((you.lastCmd or {}).get("moveX", 0.0)),
                    "moveY": float((you.lastCmd or {}).get("moveY", 0.0)),
                    "sprint": bool((you.lastCmd or {}).get("sprint", False)),
                    "jump": bool((you.lastCmd or {}).get("jump", False)),
                },
            },
            "others": others,
            "projectiles": projs,
            "pickups": picks,
            "events": events,
        }

    async def broadcast_snapshots(self, hub) -> None:
        # Clear global event queue once per snapshot broadcast.
        # Per-player events are popped in _snapshot_for.
        global_events = self._events
        self._events = []

        # Snapshot per connection (because "you" differs and per-player events).
        for conn in hub.connections_in_room(self.room_id):
            snap = self._snapshot_for(conn.player_id)
            # restore global events for next conn; _snapshot_for reads per-player queue only.
            snap["events"] = list(global_events) + list(snap.get("events", []))
            await hub.send_snapshot(conn, room=self, snapshot=snap)
