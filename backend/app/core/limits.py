import time
from collections import deque


class SlidingWindowLimiter:
    """
    In-memory sliding window rate limiter, keyed by client (IP).

    Good enough for a single-process demo. With several workers or instances each one would
    keep its own counters, so move this to Redis (INCR + EXPIRE or a sorted set) before scaling out.
    """

    def __init__(self, limit: int, window_s: float, clock=time.monotonic) -> None:
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> float | None:
        """Record a hit. Returns None if allowed, otherwise seconds until the client may retry."""
        now = self._clock()
        self._evict_idle(now)
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return self.window_s - (now - hits[0])
        hits.append(now)
        return None

    def _evict_idle(self, now: float) -> None:
        """Drop clients with no recent hits so the dict does not grow forever."""
        if len(self._hits) < 1024:
            return
        stale = [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self.window_s]
        for key in stale:
            del self._hits[key]


class ConcurrencyGate:
    """
    Caps simultaneous generations. Non-blocking: callers get an immediate 'busy' instead of queueing.

    Every slot expires after `ttl_s`, so a slot that is never released (client vanished before the
    stream started, a bug) cannot block the service forever.
    """

    def __init__(self, max_concurrent: int, ttl_s: float = 300.0, clock=time.monotonic) -> None:
        self.max_concurrent = max_concurrent
        self.ttl_s = ttl_s
        self._clock = clock
        self._slots: dict[int, float] = {}
        self._next_id = 0

    def try_acquire(self) -> int | None:
        now = self._clock()
        self._slots = {sid: t for sid, t in self._slots.items() if now - t < self.ttl_s}
        if len(self._slots) >= self.max_concurrent:
            return None
        self._next_id += 1
        self._slots[self._next_id] = now
        return self._next_id

    def release(self, slot_id: int) -> None:
        self._slots.pop(slot_id, None)

    @property
    def active(self) -> int:
        return len(self._slots)
