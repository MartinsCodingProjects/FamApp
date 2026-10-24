"""Fixed-window rate limiter in memory, timed by the Clock.

Per api process; good enough for single-process deployments. 1.10.7 adds the limits for
pairing, refresh and login keyed by the real client IP (1.10.6).
"""

from __future__ import annotations

import threading
from datetime import timedelta

from app.clock import Clock


class RateLimiter:
    def __init__(self, limit: int, window: timedelta, clock: Clock) -> None:
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def _window_start(self) -> float:
        seconds = self.window.total_seconds()
        return self.clock.now().timestamp() // seconds * seconds

    def blocked(self, key: str) -> bool:
        start = self._window_start()
        with self._lock:
            window, count = self._hits.get(key, (start, 0))
            return window == start and count >= self.limit

    def hit(self, key: str) -> None:
        start = self._window_start()
        with self._lock:
            window, count = self._hits.get(key, (start, 0))
            self._hits[key] = (start, count + 1 if window == start else 1)
            # drop stale keys so memory stays bounded
            for stale in [k for k, (w, _) in self._hits.items() if w != start]:
                del self._hits[stale]

    def retry_after(self) -> int:
        """Seconds until the current window ends (for a Retry-After header)."""
        seconds = self.window.total_seconds()
        return max(1, int(seconds - self.clock.now().timestamp() % seconds))
