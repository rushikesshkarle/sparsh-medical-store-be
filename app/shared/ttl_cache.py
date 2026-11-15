"""A tiny in-process TTL cache for hot, public, read-only queries.

Each server worker keeps its own copy. Writes clear the local copy at once; a
copy in another worker refreshes within ``ttl_seconds``, so a product change
shows up on the storefront within that window.
"""

import time
from typing import Any, Hashable


class TTLCache:
    def __init__(self, ttl_seconds: float, max_entries: int) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._data: dict[Hashable, tuple[float, Any]] = {}

    def get(self, key: Hashable) -> Any | None:
        """Return the cached value, or None if missing or expired."""
        hit = self._data.get(key)
        if hit is None:
            return None
        expires_at, value = hit
        if expires_at < time.monotonic():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: Hashable, value: Any) -> None:
        """Store a value; when full, drop the entry that expires first."""
        if len(self._data) >= self._max and key not in self._data:
            oldest = min(self._data, key=lambda k: self._data[k][0])
            self._data.pop(oldest, None)
        self._data[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        self._data.clear()
