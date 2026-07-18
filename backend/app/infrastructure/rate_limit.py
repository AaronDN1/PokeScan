"""Recognition-specific rate limiting with an optional Redis backend."""

from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from redis.asyncio import Redis


class RecognitionRateLimiter:
    """Use Redis counters in production and a bounded process-local window locally."""

    def __init__(self, *, limit: int, redis_url: str | None) -> None:
        self._limit = limit
        self._redis = Redis.from_url(redis_url, decode_responses=True) if redis_url else None
        self._local: dict[str, deque[float]] = defaultdict(deque)

    async def allow(self, key: str) -> bool:
        """Return whether the caller may start another recognition request."""
        if self._redis is not None:
            bucket = f"recognition-rate:{key}"
            try:
                count = int(await self._redis.incr(bucket))
                if count == 1:
                    await self._redis.expire(bucket, 60)
                return count <= self._limit
            except Exception:
                # Availability degrades to a stricter per-process limiter.
                pass
        now = monotonic()
        window = self._local[key]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= self._limit:
            return False
        window.append(now)
        return True

    async def close(self) -> None:
        """Close the optional Redis client during application shutdown."""
        if self._redis is not None:
            await self._redis.aclose()
