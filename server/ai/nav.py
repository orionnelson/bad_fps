"""A* over a simple 2D grid (phase1 navigation)."""

from __future__ import annotations

import heapq
import math
from typing import Any


class GridNav:
    def __init__(self, map_data, cell_size: float, pad: float):
        self.map = map_data
        self.cell = float(cell_size)
        self.pad = float(pad)

        self.minx = map_data.bounds.min[0]
        self.minz = map_data.bounds.min[2]
        self.maxx = map_data.bounds.max[0]
        self.maxz = map_data.bounds.max[2]

        self.w = max(1, int(math.ceil((self.maxx - self.minx) / self.cell)))
        self.h = max(1, int(math.ceil((self.maxz - self.minz) / self.cell)))
        self.blocked = [[False for _ in range(self.h)] for _ in range(self.w)]
        self._build()

    def _cell_center(self, ix: int, iz: int) -> tuple[float, float]:
        x = self.minx + (ix + 0.5) * self.cell
        z = self.minz + (iz + 0.5) * self.cell
        return x, z

    def _build(self) -> None:
        # Mark cells blocked if their center is inside any collider expanded by pad.
        for ix in range(self.w):
            for iz in range(self.h):
                x, z = self._cell_center(ix, iz)
                for a in self.map.colliders:
                    if (a.min[0] - self.pad) <= x <= (a.max[0] + self.pad) and (a.min[2] - self.pad) <= z <= (a.max[2] + self.pad):
                        self.blocked[ix][iz] = True
                        break

    def _to_cell(self, pos: list[float]) -> tuple[int, int]:
        ix = int((pos[0] - self.minx) / self.cell)
        iz = int((pos[2] - self.minz) / self.cell)
        ix = 0 if ix < 0 else self.w - 1 if ix >= self.w else ix
        iz = 0 if iz < 0 else self.h - 1 if iz >= self.h else iz
        return ix, iz

    def _nearest_unblocked(self, cell: tuple[int, int], max_r: int = 8) -> tuple[int, int] | None:
        x0, z0 = cell
        if 0 <= x0 < self.w and 0 <= z0 < self.h and not self.blocked[x0][z0]:
            return cell
        for r in range(1, max_r + 1):
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if abs(dx) != r and abs(dz) != r:
                        continue
                    x = x0 + dx
                    z = z0 + dz
                    if 0 <= x < self.w and 0 <= z < self.h and not self.blocked[x][z]:
                        return (x, z)
        return None

    def _heur(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _neighbors(self, n: tuple[int, int]):
        x, z = n
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
            nx, nz = x + dx, z + dz
            if 0 <= nx < self.w and 0 <= nz < self.h and not self.blocked[nx][nz]:
                yield (nx, nz)

    def plan(self, start_pos: list[float], goal_pos: list[float], max_nodes: int = 1200) -> list[tuple[float, float]]:
        start0 = self._to_cell(start_pos)
        goal0 = self._to_cell(goal_pos)
        start = self._nearest_unblocked(start0)
        goal = self._nearest_unblocked(goal0)
        if start is None or goal is None:
            return []
        if start == goal:
            x, z = self._cell_center(start[0], start[1])
            return [(x, z)]

        openq: list[tuple[float, tuple[int, int]]] = []
        heapq.heappush(openq, (0.0, start))
        came: dict[tuple[int, int], tuple[int, int]] = {}
        g = {start: 0.0}

        visited = 0
        while openq and visited < max_nodes:
            visited += 1
            _, cur = heapq.heappop(openq)
            if cur == goal:
                break
            for nb in self._neighbors(cur):
                step = 1.0 if (nb[0] == cur[0] or nb[1] == cur[1]) else 1.4
                ng = g[cur] + step
                if ng < g.get(nb, 1e30):
                    g[nb] = ng
                    came[nb] = cur
                    f = ng + self._heur(nb, goal)
                    heapq.heappush(openq, (f, nb))

        if goal not in came:
            return []

        path = [goal]
        cur = goal
        while cur != start:
            cur = came[cur]
            path.append(cur)
        path.reverse()
        out = [self._cell_center(ix, iz) for (ix, iz) in path]
        return out

    def next_direction(self, from_pos: list[float], to_pos: list[float]) -> tuple[float, float]:
        path = self.plan(from_pos, to_pos)
        if len(path) < 2:
            dx = to_pos[0] - from_pos[0]
            dz = to_pos[2] - from_pos[2]
        else:
            dx = path[1][0] - from_pos[0]
            dz = path[1][1] - from_pos[2]
        l = (dx * dx + dz * dz) ** 0.5
        if l <= 1e-6:
            return 0.0, 0.0
        return dx / l, dz / l
