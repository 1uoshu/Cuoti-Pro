from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Protocol

from redis import Redis
from redis.exceptions import RedisError


class RedisStore(Protocol):
    def ping(self) -> bool: ...

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, *, ex: int | None = None) -> None: ...

    def delete(self, *keys: str) -> int: ...

    def getdel(self, key: str) -> str | None: ...

    def sadd(self, key: str, *values: str) -> int: ...

    def smembers(self, key: str) -> set[str]: ...

    def expire(self, key: str, seconds: int) -> bool: ...


class RedisClient:
    def __init__(self, url: str) -> None:
        self._client = Redis.from_url(url, decode_responses=True)

    def ping(self) -> bool:
        return bool(self._client.ping())

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        self._client.set(key, value, ex=ex)

    def delete(self, *keys: str) -> int:
        return int(self._client.delete(*keys)) if keys else 0

    def getdel(self, key: str) -> str | None:
        return self._client.getdel(key)

    def sadd(self, key: str, *values: str) -> int:
        return int(self._client.sadd(key, *values)) if values else 0

    def smembers(self, key: str) -> set[str]:
        return set(self._client.smembers(key))

    def expire(self, key: str, seconds: int) -> bool:
        return bool(self._client.expire(key, seconds))


class InMemoryRedisClient:
    """Test-only Redis-compatible store used when APP_ENV=test and REDIS_URL=memory://."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._sets: defaultdict[str, set[str]] = defaultdict(set)
        self._expires_at: dict[str, datetime] = {}
        self._lock = Lock()

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> str | None:
        with self._lock:
            self._purge(key)
            return self._values.get(key)

    def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        with self._lock:
            self._values[key] = value
            self._set_expiry(key, ex)

    def delete(self, *keys: str) -> int:
        with self._lock:
            deleted = 0
            for key in keys:
                self._purge(key)
                if key in self._values or key in self._sets:
                    deleted += 1
                self._values.pop(key, None)
                self._sets.pop(key, None)
                self._expires_at.pop(key, None)
            return deleted

    def getdel(self, key: str) -> str | None:
        with self._lock:
            self._purge(key)
            value = self._values.pop(key, None)
            self._expires_at.pop(key, None)
            return value

    def sadd(self, key: str, *values: str) -> int:
        with self._lock:
            self._purge(key)
            existing = self._sets[key]
            size_before = len(existing)
            existing.update(values)
            return len(existing) - size_before

    def smembers(self, key: str) -> set[str]:
        with self._lock:
            self._purge(key)
            return set(self._sets.get(key, set()))

    def expire(self, key: str, seconds: int) -> bool:
        with self._lock:
            self._purge(key)
            if key not in self._values and key not in self._sets:
                return False
            self._set_expiry(key, seconds)
            return True

    def _set_expiry(self, key: str, seconds: int | None) -> None:
        if seconds is None:
            self._expires_at.pop(key, None)
        else:
            self._expires_at[key] = datetime.now(UTC) + timedelta(seconds=seconds)

    def _purge(self, key: str) -> None:
        expires_at = self._expires_at.get(key)
        if expires_at and expires_at <= datetime.now(UTC):
            self._values.pop(key, None)
            self._sets.pop(key, None)
            self._expires_at.pop(key, None)


def build_redis_client(url: str, *, test_mode: bool) -> RedisStore:
    if url == "memory://" and test_mode:
        return InMemoryRedisClient()
    return RedisClient(url)


def ensure_redis_available(redis: RedisStore) -> None:
    try:
        redis.ping()
    except RedisError as error:
        raise RuntimeError("Redis 不可用，后端拒绝以无状态 JWT 模式启动") from error
