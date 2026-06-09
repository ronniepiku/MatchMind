"""In-memory response cache with TTL for API endpoints.

Caches JSON-serializable responses to avoid redundant DB queries.
Designed for read-heavy workloads where data changes infrequently
(e.g., teams/seasons/player lists rarely update).

Thread-safe via threading.Lock.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_MAX_ENTRIES = 512


def _evict_expired() -> None:
    """Remove expired entries (called under lock)."""
    now = time.time()
    expired = [k for k, (exp, _) in _cache.items() if exp <= now]
    for k in expired:
        del _cache[k]


def cache_key(prefix: str, **kwargs: Any) -> str:
    """Generate a deterministic cache key."""
    params = "&".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)
    raw = f"{prefix}:{params}"
    return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324


def get(key: str) -> Any | None:
    """Get a cached value if it exists and hasn't expired."""
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.time() >= expires:
            del _cache[key]
            return None
        # Move to end (LRU)
        _cache.move_to_end(key)
        return value


def put(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Store a value with a TTL."""
    with _lock:
        _cache[key] = (time.time() + ttl_seconds, value)
        # Enforce max size
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)


def invalidate(prefix: str | None = None) -> int:
    """Invalidate cache entries. If prefix is None, clear all."""
    with _lock:
        if prefix is None:
            count = len(_cache)
            _cache.clear()
            return count
        # Prefix-based invalidation
        to_remove = [k for k in _cache if k.startswith(prefix)]
        for k in to_remove:
            del _cache[k]
        return len(to_remove)


def stats() -> dict[str, Any]:
    """Return cache statistics."""
    with _lock:
        _evict_expired()
        return {"entries": len(_cache), "max_entries": _MAX_ENTRIES}
