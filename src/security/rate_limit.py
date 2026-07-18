"""Small per-process sliding-window limiter for the public chat endpoint."""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class SlidingWindowRateLimiter:
    """Bound requests per client key without retaining IP addresses in logs or storage."""

    def __init__(
        self,
        limit: int,
        *,
        window_seconds: float = 60.0,
        max_client_keys: int = 10_000,
    ) -> None:
        if limit <= 0 or window_seconds <= 0 or max_client_keys <= 0:
            raise ValueError("Rate-limit values must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_client_keys = max_client_keys
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, *, now: float | None = None) -> float | None:
        """Record an allowed request or return seconds until the oldest request expires."""
        observed = monotonic() if now is None else now
        cutoff = observed - self.window_seconds
        with self._lock:
            if key not in self._requests and len(self._requests) >= self.max_client_keys:
                self._requests.pop(next(iter(self._requests)))
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                return max(0.0, self.window_seconds - (observed - requests[0]))
            requests.append(observed)
            return None
