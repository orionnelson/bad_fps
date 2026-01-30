"""World state container + map loading."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


def v3(x: float, y: float, z: float) -> list[float]:
    return [float(x), float(y), float(z)]


def v3_add(a: list[float], b: list[float]) -> list[float]:
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def v3_sub(a: list[float], b: list[float]) -> list[float]:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def v3_mul(a: list[float], s: float) -> list[float]:
    return [a[0] * s, a[1] * s, a[2] * s]


def v3_dot(a: list[float], b: list[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v3_len(a: list[float]) -> float:
    return (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) ** 0.5


def v3_norm(a: list[float]) -> list[float]:
    l = v3_len(a)
    if l <= 1e-9:
        return [0.0, 0.0, 0.0]
    return [a[0] / l, a[1] / l, a[2] / l]


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


@dataclass
class AABB:
    min: list[float]
    max: list[float]

    @classmethod
    def from_center_size(cls, cx: float, cy: float, cz: float, sx: float, sy: float, sz: float) -> "AABB":
        hx, hy, hz = sx * 0.5, sy * 0.5, sz * 0.5
        return cls(min=[cx - hx, cy - hy, cz - hz], max=[cx + hx, cy + hy, cz + hz])


@dataclass
class MapData:
    mapId: str
    bounds: AABB
    colliders: list[AABB]
    spawns: list[list[float]]
    pickups: list[dict[str, Any]]


def load_map(map_id: str) -> MapData:
    here = os.path.dirname(os.path.abspath(__file__))
    maps_dir = os.path.join(here, "maps")
    path = os.path.join(maps_dir, f"{map_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    bounds = AABB.from_center_size(
        data["bounds"]["center"][0],
        data["bounds"]["center"][1],
        data["bounds"]["center"][2],
        data["bounds"]["size"][0],
        data["bounds"]["size"][1],
        data["bounds"]["size"][2],
    )

    colliders = []
    for c in data.get("colliders", []):
        colliders.append(
            AABB.from_center_size(
                c["center"][0], c["center"][1], c["center"][2], c["size"][0], c["size"][1], c["size"][2]
            )
        )
    spawns = [v3(*p) for p in data.get("spawns", [])]
    pickups = list(data.get("pickups", []))

    return MapData(mapId=data.get("mapId", map_id), bounds=bounds, colliders=colliders, spawns=spawns, pickups=pickups)
