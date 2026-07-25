import json
import hashlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis as redis_lib
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class Cache:
    """Simple caching layer with Redis backend and fallback to in-memory dict."""

    def __init__(self):
        self._redis = None
        self._memory: dict[str, tuple[Any, float]] = {}
        self._default_ttl = 300  # 5 minutes

    def init_app(self, redis_url: Optional[str] = None):
        if REDIS_AVAILABLE and redis_url:
            try:
                self._redis = redis_lib.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("Redis cache connected")
                return
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory cache: {e}")
        logger.info("Using in-memory cache (install redis for better performance)")

    def _make_key(self, prefix: str, **params) -> str:
        raw = json.dumps(params, sort_keys=True)
        return f"{prefix}:{hashlib.md5(raw.encode()).hexdigest()}"

    def get(self, prefix: str, **params) -> Optional[Any]:
        key = self._make_key(prefix, **params)
        if self._redis:
            val = self._redis.get(key)
            return json.loads(val) if val else None
        entry = self._memory.get(key)
        if entry:
            val, expiry = entry
            if expiry > __import__("time").time():
                return val
            del self._memory[key]
        return None

    def set(self, prefix: str, value: Any, ttl: Optional[int] = None, **params):
        key = self._make_key(prefix, **params)
        ttl = ttl or self._default_ttl
        if self._redis:
            self._redis.setex(key, ttl, json.dumps(value))
        else:
            self._memory[key] = (value, __import__("time").time() + ttl)

    def invalidate(self, prefix: str, **params):
        key = self._make_key(prefix, **params)
        if self._redis:
            self._redis.delete(key)
        else:
            self._memory.pop(key, None)

    def clear(self):
        if self._redis:
            self._redis.flushdb()
        self._memory.clear()


cache = Cache()
