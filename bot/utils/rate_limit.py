import time
from collections import defaultdict


class RateLimiter:
    """Simple per-user rate limiter."""

    def __init__(self, min_interval: float = 1.5):
        self._last: dict[int, float] = defaultdict(float)
        self._interval = min_interval

    def is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()
        if now - self._last[user_id] >= self._interval:
            self._last[user_id] = now
            return True
        return False
