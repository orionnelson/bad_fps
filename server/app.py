"""HTTP + WebSocket entrypoint (server authoritative).

This server intentionally does NOT serve the web client. Host `client/` separately.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import asdict
from typing import Any

from aiohttp import web

from server.game.config import ServerConfig
from server.net.ws import WsHub
from server.storage.memory import MemoryStore
from server.storage.sqlite import SqliteStore


class GameService:
    def __init__(self, config: ServerConfig):
        self.config = config
        self.server_id = str(uuid.uuid4())
        self.start_time = time.time()

        self.memory = MemoryStore()
        self.sqlite = SqliteStore(self.config.sqlite_path) if self.config.sqlite_enabled else None

        self.hub = WsHub(self)
        self.rooms = {}

        self._running = False
        self._tick_task: asyncio.Task | None = None

        self._tick = 0

    @property
    def tick(self) -> int:
        return self._tick

    def now(self) -> float:
        return time.time()

    async def start(self) -> None:
        if self.sqlite:
            self.sqlite.init()
        self._running = True
        self._tick_task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        self._running = False
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass

        await self.hub.close_all()
        if self.sqlite:
            self.sqlite.close()

    async def _tick_loop(self) -> None:
        tick_dt = 1.0 / float(self.config.simulation_hz)
        snap_every = max(1, int(round(self.config.simulation_hz / float(self.config.snapshot_hz))))

        last = time.perf_counter()
        acc = 0.0
        while self._running:
            now = time.perf_counter()
            acc += now - last
            last = now

            # Prevent spiral of death.
            if acc > 0.25:
                acc = 0.25

            stepped = False
            while acc >= tick_dt:
                acc -= tick_dt
                self._tick += 1
                stepped = True
                for room in list(self.rooms.values()):
                    room.step(self._tick, tick_dt)

                if (self._tick % snap_every) == 0:
                    for room in list(self.rooms.values()):
                        await room.broadcast_snapshots(self.hub)

            if not stepped:
                await asyncio.sleep(0.001)

    def get_or_create_room(self, room_id: str, map_id: str | None = None):
        from server.game.room import Room

        room = self.rooms.get(room_id)
        if room:
            return room

        if len(self.rooms) >= self.config.max_rooms:
            raise web.HTTPTooManyRequests(text="server at room capacity")

        room = Room(
            room_id=room_id,
            map_id=map_id or self.config.default_map_id,
            config=self.config,
            memory=self.memory,
            sqlite=self.sqlite,
        )
        self.rooms[room_id] = room
        return room

    def matchmake(self, map_id: str | None = None) -> str:
        # Find any room with capacity.
        for room in self.rooms.values():
            if room.map_id == (map_id or room.map_id) and len(room.players) < self.config.max_players_per_room:
                return room.room_id
        room_id = uuid.uuid4().hex[:8]
        self.get_or_create_room(room_id, map_id=map_id)
        return room_id

    def version_payload(self) -> dict[str, Any]:
        return {
            "serverId": self.server_id,
            "serverVersion": self.config.server_version,
            "protocolVersion": self.config.protocol_version,
            "simulationHz": self.config.simulation_hz,
            "snapshotHz": self.config.snapshot_hz,
        }


def _cors_headers(config: ServerConfig, origin: str | None) -> dict[str, str]:
    if not origin:
        return {}
    if config.cors_allow_all:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    if origin in config.cors_allowed_origins:
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
    return {}


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin")
        headers = {
            **_cors_headers(request.app["config"], origin),
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
        }
        return web.Response(status=204, headers=headers)

    resp = await handler(request)

    # WebSockets do not use CORS like fetch/XHR, and aiohttp finalizes WS headers
    # during `prepare()`. Avoid mutating headers after the handshake.
    if isinstance(resp, web.WebSocketResponse):
        return resp

    origin = request.headers.get("Origin")
    for k, v in _cors_headers(request.app["config"], origin).items():
        try:
            resp.headers[k] = v
        except Exception:
            # If headers are already sent/prepared, just skip.
            pass
    return resp


def create_app(config: ServerConfig) -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    svc = GameService(config)

    app["config"] = config
    app["svc"] = svc

    async def on_startup(_: web.Application):
        await svc.start()

    async def on_cleanup(_: web.Application):
        await svc.stop()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    async def health(_: web.Request):
        return web.json_response(
            {
                "ok": True,
                "uptimeSec": time.time() - svc.start_time,
                "rooms": len(svc.rooms),
                "players": sum(r.player_count for r in svc.rooms.values()),
                **svc.version_payload(),
            }
        )

    async def root(_: web.Request):
        return web.json_response(
            {
                "ok": True,
                "service": "fps-server",
                **svc.version_payload(),
                "endpoints": {
                    "health": "/health",
                    "version": "/version",
                    "rooms": "/rooms",
                    "matchmake": "/matchmake",
                    "leaderboard": "/leaderboard",
                    "schema": "/schema",
                    "ws": "/ws",
                },
            }
        )

    async def version(_: web.Request):
        return web.json_response(svc.version_payload())

    async def rooms(_: web.Request):
        return web.json_response(
            {
                "rooms": [r.public_info() for r in svc.rooms.values()],
            }
        )

    async def matchmake(request: web.Request):
        body = {}
        if request.can_read_body:
            try:
                body = await request.json()
            except Exception:
                body = {}
        map_id = body.get("mapId") if isinstance(body, dict) else None
        room_id = svc.matchmake(map_id=map_id)
        return web.json_response({"roomId": room_id})

    async def leaderboard(_: web.Request):
        top = svc.sqlite.get_leaderboard(limit=25) if svc.sqlite else svc.memory.get_leaderboard(limit=25)
        return web.json_response({"leaderboard": top})

    async def schema(_: web.Request):
        here = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(os.path.dirname(here), "shared", "schema.json")
        # In case the shared folder isn't deployed alongside server.
        if not os.path.exists(schema_path):
            schema_path = os.path.join(here, "..", "shared", "schema.json")
            schema_path = os.path.abspath(schema_path)
        if not os.path.exists(schema_path):
            raise web.HTTPNotFound(text="schema.json not found")
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return web.json_response(data)

    async def ws_handler(request: web.Request):
        return await svc.hub.handle(request)

    app.router.add_get("/", root)
    app.router.add_get("/health", health)
    app.router.add_get("/version", version)
    app.router.add_get("/rooms", rooms)
    app.router.add_post("/matchmake", matchmake)
    app.router.add_get("/leaderboard", leaderboard)
    app.router.add_get("/schema", schema)
    app.router.add_get("/ws", ws_handler)
    app.router.add_route("OPTIONS", "/{tail:.*}", lambda r: web.Response(status=204))

    return app


def main() -> None:
    config = ServerConfig.from_env()
    app = create_app(config)
    web.run_app(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
