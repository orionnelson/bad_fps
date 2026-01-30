"""Message schemas + validation.

Wire format:
  {"type": "input", "data": {...}}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class ProtocolError(Exception):
    pass


def dumps(msg_type: str, data: dict[str, Any]) -> str:
    return json.dumps({"type": msg_type, "data": data}, separators=(",", ":"))


def loads(text: str) -> tuple[str, dict[str, Any]]:
    try:
        obj = json.loads(text)
    except Exception as e:
        raise ProtocolError(f"invalid json: {e}")

    if not isinstance(obj, dict):
        raise ProtocolError("message must be object")
    t = obj.get("type")
    if not isinstance(t, str):
        raise ProtocolError("missing type")
    data = obj.get("data")
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ProtocolError("data must be object")
    return t, data


def _num(v: Any, *, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _int(v: Any, *, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _bool(v: Any) -> bool:
    return bool(v)


@dataclass
class Hello:
    clientVersion: str
    preferredRegion: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "Hello":
        v = data.get("clientVersion")
        if not isinstance(v, str) or not v:
            raise ProtocolError("hello.clientVersion required")
        pr = data.get("preferredRegion")
        if pr is not None and not isinstance(pr, str):
            pr = None
        return cls(clientVersion=v, preferredRegion=pr)


@dataclass
class Join:
    roomId: str | None
    matchmake: bool
    playerName: str
    wantDeltas: bool

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "Join":
        room_id = data.get("roomId")
        if room_id is not None and not isinstance(room_id, str):
            room_id = None
        matchmake = _bool(data.get("matchmake"))
        name = data.get("playerName")
        if not isinstance(name, str) or not name.strip():
            name = "Player"
        want_deltas = bool(data.get("wantDeltas", True))
        return cls(roomId=room_id, matchmake=matchmake, playerName=name[:24], wantDeltas=want_deltas)


@dataclass
class Input:
    seq: int
    dt: float
    moveX: float
    moveY: float
    jump: bool
    sprint: bool
    yaw: float
    pitch: float
    fire: bool
    weaponId: str
    reload: bool

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "Input":
        seq = _int(data.get("seq"), default=-1)
        if seq < 0:
            raise ProtocolError("input.seq required")
        dt = _num(data.get("dt"), default=0.016)
        move_x = max(-1.0, min(1.0, _num(data.get("moveX"), default=0.0)))
        move_y = max(-1.0, min(1.0, _num(data.get("moveY"), default=0.0)))
        yaw = _num(data.get("yaw"), default=0.0)
        pitch = _num(data.get("pitch"), default=0.0)
        weapon_id = data.get("weaponId")
        if not isinstance(weapon_id, str) or not weapon_id:
            weapon_id = "pistol"
        return cls(
            seq=seq,
            dt=dt,
            moveX=move_x,
            moveY=move_y,
            jump=_bool(data.get("jump")),
            sprint=_bool(data.get("sprint")),
            yaw=yaw,
            pitch=pitch,
            fire=_bool(data.get("fire")),
            weaponId=weapon_id,
            reload=_bool(data.get("reload")),
        )


@dataclass
class Chat:
    text: str

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "Chat":
        t = data.get("text")
        if not isinstance(t, str):
            raise ProtocolError("chat.text required")
        t = t.strip()
        if not t:
            raise ProtocolError("chat.text empty")
        return cls(text=t[:160])


@dataclass
class Ping:
    t: float

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "Ping":
        return cls(t=_num(data.get("t"), default=0.0))


VALID_C2S = {"hello", "join", "input", "chat", "leave", "ping"}
