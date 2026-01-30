"""Per-client quotas (token bucket)."""

from __future__ import annotations

import time


class TokenBucket:
    def __init__(self, rate_per_sec: float, burst: float):
        self.rate = float(rate_per_sec)
        self.capacity = float(burst)
        self.tokens = float(burst)
        self.last = time.perf_counter()

    def allow(self, cost: float = 1.0) -> bool:
        now = time.perf_counter()
        dt = now - self.last
        self.last = now
        self.tokens = min(self.capacity, self.tokens + dt * self.rate)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False
