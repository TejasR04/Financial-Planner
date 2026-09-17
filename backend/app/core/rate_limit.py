"""Small process-local controls for expensive public endpoints.

These controls protect a single API worker. Deployments with multiple workers
should additionally enforce shared limits at the reverse proxy or API gateway.
"""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        timestamp = monotonic() if now is None else now
        cutoff = timestamp - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(timestamp)
            return True


class PerKeyConcurrencyLimiter:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._active: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def acquire(self, key: str) -> bool:
        with self._lock:
            if self._active[key] >= self.limit:
                return False
            self._active[key] += 1
            return True

    def release(self, key: str) -> None:
        with self._lock:
            active = self._active.get(key, 0)
            if active <= 1:
                self._active.pop(key, None)
            else:
                self._active[key] = active - 1
