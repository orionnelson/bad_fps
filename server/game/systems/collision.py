"""Broadphase + narrowphase helpers.

This is intentionally simple: players are treated as spheres for obstacle resolution,
and as two spheres (head/body) for hitscan.
"""

from __future__ import annotations

import math
from typing import Iterable

from server.game.world import AABB, v3_add, v3_dot, v3_mul, v3_sub, v3_len, v3_norm


def closest_point_aabb(p: list[float], a: AABB) -> list[float]:
    return [
        a.min[0] if p[0] < a.min[0] else a.max[0] if p[0] > a.max[0] else p[0],
        a.min[1] if p[1] < a.min[1] else a.max[1] if p[1] > a.max[1] else p[1],
        a.min[2] if p[2] < a.min[2] else a.max[2] if p[2] > a.max[2] else p[2],
    ]


def sphere_intersects_aabb(center: list[float], radius: float, a: AABB) -> bool:
    c = closest_point_aabb(center, a)
    d = v3_sub(center, c)
    return v3_dot(d, d) <= radius * radius


def resolve_sphere_vs_aabb_xz(center: list[float], radius: float, a: AABB) -> tuple[list[float], bool]:
    # Only resolve if sphere overlaps collider in vertical span.
    if center[1] < a.min[1] - radius or center[1] > a.max[1] + radius:
        return center, False

    c = closest_point_aabb(center, a)
    d = v3_sub(center, c)
    d[1] = 0.0
    dist2 = v3_dot(d, d)
    if dist2 > radius * radius:
        return center, False

    if dist2 < 1e-9:
        # Center is inside; push out along nearest face in XZ.
        left = abs(center[0] - a.min[0])
        right = abs(a.max[0] - center[0])
        back = abs(center[2] - a.min[2])
        front = abs(a.max[2] - center[2])
        m = min(left, right, back, front)
        if m == left:
            d = [1.0, 0.0, 0.0]
        elif m == right:
            d = [-1.0, 0.0, 0.0]
        elif m == back:
            d = [0.0, 0.0, 1.0]
        else:
            d = [0.0, 0.0, -1.0]
        dist = 0.0
    else:
        dist = dist2 ** 0.5
        d = v3_mul(d, 1.0 / dist)

    push = radius - dist
    out = [center[0] + d[0] * push, center[1], center[2] + d[2] * push]
    return out, True


def ray_aabb(origin: list[float], direction: list[float], a: AABB) -> float | None:
    # Slab method; direction must be normalized.
    tmin = -1e30
    tmax = 1e30
    for i in range(3):
        o = origin[i]
        d = direction[i]
        amin = a.min[i]
        amax = a.max[i]
        if abs(d) < 1e-9:
            if o < amin or o > amax:
                return None
            continue
        inv = 1.0 / d
        t1 = (amin - o) * inv
        t2 = (amax - o) * inv
        if t1 > t2:
            t1, t2 = t2, t1
        tmin = max(tmin, t1)
        tmax = min(tmax, t2)
        if tmin > tmax:
            return None
    if tmax < 0.0:
        return None
    return tmin if tmin >= 0.0 else tmax


def ray_sphere(origin: list[float], direction: list[float], center: list[float], radius: float) -> float | None:
    oc = v3_sub(origin, center)
    b = 2.0 * v3_dot(oc, direction)
    c = v3_dot(oc, oc) - radius * radius
    disc = b * b - 4.0 * c
    if disc < 0.0:
        return None
    s = disc ** 0.5
    t1 = (-b - s) * 0.5
    t2 = (-b + s) * 0.5
    if t1 >= 0.0:
        return t1
    if t2 >= 0.0:
        return t2
    return None


def first_obstacle_hit(origin: list[float], direction: list[float], colliders: Iterable[AABB], max_dist: float) -> float | None:
    best = None
    for a in colliders:
        t = ray_aabb(origin, direction, a)
        if t is None or t > max_dist:
            continue
        if best is None or t < best:
            best = t
    return best
