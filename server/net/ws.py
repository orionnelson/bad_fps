"""WebSocket handlers."""

from __future__ import annotations

import asyncio
import math
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from aiohttp import WSMsgType, web

from server.game import protocol
from server.net.rate_limit import TokenBucket
from server.net.snapshots import SnapshotCache


@dataclass
class Connection:
    conn_id: str
    ws: web.WebSocketResponse
    created_at: float

    player_id: str
    player_name: str
    room_id: str | None
    hello_version: str | None
    want_deltas: bool

    input_bucket: TokenBucket
    chat_bucket: TokenBucket


class WsHub:
    def __init__(self, svc):
        self.svc = svc
        self._conns: dict[str, Connection] = {}
        self._snapshot_cache = SnapshotCache()

    def _origin_allowed(self, origin: str | None) -> bool:
        cfg = self.svc.config
        if cfg.cors_allow_all:
            return True
        if not origin:
            return False
        return origin in cfg.cors_allowed_origins

    async def handle(self, request: web.Request) -> web.StreamResponse:
        if not self._origin_allowed(request.headers.get("Origin")):
            raise web.HTTPForbidden(text="origin not allowed")

        ws = web.WebSocketResponse(heartbeat=10.0, max_msg_size=1_000_000)
        await ws.prepare(request)

        conn_id = uuid.uuid4().hex
        player_id = uuid.uuid4().hex
        conn = Connection(
            conn_id=conn_id,
            ws=ws,
            created_at=time.time(),
            player_id=player_id,
            player_name="Player",
            room_id=None,
            hello_version=None,
            want_deltas=True,
            input_bucket=TokenBucket(rate_per_sec=120.0, burst=240.0),
            chat_bucket=TokenBucket(rate_per_sec=1.5, burst=3.0),
        )
        self._conns[conn_id] = conn

        await ws.send_str(protocol.dumps("info", {"server": self.svc.version_payload()}))

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._on_text(conn, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    break
        finally:
            await self._disconnect(conn)
        return ws

    async def _on_text(self, conn: Connection, text: str) -> None:
        try:
            msg_type, data = protocol.loads(text)
        except protocol.ProtocolError as e:
            await conn.ws.send_str(protocol.dumps("error", {"message": str(e)}))
            return

        if msg_type not in protocol.VALID_C2S:
            await conn.ws.send_str(protocol.dumps("error", {"message": "invalid type"}))
            return

        if msg_type == "hello":
            h = protocol.Hello.parse(data)
            conn.hello_version = h.clientVersion
            await conn.ws.send_str(
                protocol.dumps(
                    "version",
                    {
                        "ok": True,
                        **self.svc.version_payload(),
                    },
                )
            )
            return

        if msg_type == "join":
            j = protocol.Join.parse(data)
            conn.player_name = j.playerName
            # Always send full snapshots; simplifies client correctness.
            conn.want_deltas = False
            room_id = j.roomId
            if j.matchmake or not room_id:
                room_id = self.svc.matchmake()
            room = self.svc.get_or_create_room(room_id)
            room.add_player(conn.player_id, conn.player_name)
            conn.room_id = room_id
            self._snapshot_cache.clear(conn.player_id)

            await conn.ws.send_str(
                protocol.dumps(
                    "welcome",
                    {
                        "playerId": conn.player_id,
                        "tickrate": self.svc.config.simulation_hz,
                        "roomId": room.room_id,
                        "seed": room.seed,
                        "mapId": room.map_id,
                    },
                )
            )
            return

        if msg_type == "leave":
            await self._disconnect(conn)
            return

        if msg_type == "ping":
            p = protocol.Ping.parse(data)
            await conn.ws.send_str(protocol.dumps("pong", {"t": p.t, "serverTime": time.time()}))
            return

        # Must be joined for input/chat.
        if not conn.room_id:
            await conn.ws.send_str(protocol.dumps("error", {"message": "not joined"}))
            return

        room = self.svc.rooms.get(conn.room_id)
        if not room:
            await conn.ws.send_str(protocol.dumps("error", {"message": "room missing"}))
            return

        if msg_type == "chat":
            if not conn.chat_bucket.allow():
                return
            c = protocol.Chat.parse(data)
            room._push_event("chat", {"from": conn.player_name, "text": c.text})
            return

        if msg_type == "input":
            if not conn.input_bucket.allow():
                return
            inp = protocol.Input.parse(data)
            # Validate dt & input order window.
            if inp.dt < 0.0 or inp.dt > self.svc.config.max_dt:
                return

            pl = room.players.get(conn.player_id)
            if not pl:
                return

            # Accept client aim angles (server authoritative sim still validates movement).
            # For dev feel we only normalize angles here; stricter turn-rate limits can be
            # reintroduced later without breaking client movement alignment.
            yaw = (float(inp.yaw) + math.pi) % (math.tau) - math.pi
            pitch = max(-1.4, min(1.4, float(inp.pitch)))

            # Sequence window.
            if inp.seq <= pl.lastInputSeq - self.svc.config.input_seq_window:
                return
            if inp.seq <= pl.lastInputSeq:
                # Duplicate/out-of-order; ignore.
                return

            pl.lastInputSeq = inp.seq
            # Apply as last command.
            room.apply_input(
                conn.player_id,
                {
                    "seq": inp.seq,
                    "moveX": inp.moveX,
                    "moveY": inp.moveY,
                    "jump": inp.jump,
                    "sprint": inp.sprint,
                    "yaw": yaw,
                    "pitch": pitch,
                    "fire": inp.fire,
                    "weaponId": inp.weaponId,
                    "reload": inp.reload,
                },
            )
            return

    async def _disconnect(self, conn: Connection) -> None:
        # Idempotent.
        if conn.conn_id not in self._conns:
            return
        self._conns.pop(conn.conn_id, None)
        if conn.room_id:
            room = self.svc.rooms.get(conn.room_id)
            if room:
                room.remove_player(conn.player_id)
        self._snapshot_cache.clear(conn.player_id)
        try:
            await conn.ws.close()
        except Exception:
            pass

    async def close_all(self) -> None:
        for c in list(self._conns.values()):
            await self._disconnect(c)

    def connections_in_room(self, room_id: str) -> Iterable[Connection]:
        for c in self._conns.values():
            if c.room_id == room_id:
                yield c

    async def send_snapshot(self, conn: Connection, room, snapshot: dict[str, Any]) -> None:
        payload = self._snapshot_cache.make(
            player_id=conn.player_id,
            server_tick=self.svc.tick,
            snapshot={
                "roomId": room.room_id,
                "mapId": room.map_id,
                "seed": room.seed,
                **snapshot,
            },
            want_delta=conn.want_deltas,
        )
        await conn.ws.send_str(protocol.dumps("snapshot", payload))
