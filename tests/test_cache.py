from __future__ import annotations

from redis.exceptions import RedisError

import cache
from config import get_settings


async def test_cache_falls_back_to_memory_when_redis_is_not_configured():
    await cache.set_cached("example", {"ok": True}, ttl=60)

    assert await cache.get_cached("example") == {"ok": True}
    assert await cache.cache_backend_name() == "memory"
    assert await cache.redis_status() == "not_configured"


async def test_memory_counter_fallback():
    assert await cache.increment_counter("stats:queries_served") == 1
    assert await cache.increment_counter("stats:queries_served", amount=2) == 3
    assert await cache.get_counter("stats:queries_served") == 3
    assert await cache.increment_counter_capped("stats:capped", 2) == (True, 1)
    assert await cache.increment_counter_capped("stats:capped", 2) == (True, 2)
    assert await cache.increment_counter_capped("stats:capped", 2) == (False, 2)


async def test_redis_startup_validation_pings_once(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:6379")
    get_settings.cache_clear()

    class FakeRedis:
        def __init__(self):
            self.pings = 0

        async def ping(self):
            self.pings += 1
            return True

        async def aclose(self):
            pass

    fake_client = FakeRedis()
    monkeypatch.setattr(cache.redis, "from_url", lambda *args, **kwargs: fake_client)

    assert await cache.get_client() is fake_client
    assert fake_client.pings == 1


async def test_redis_failed_ping_falls_back_to_memory(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:6379")
    get_settings.cache_clear()

    class FakeRedis:
        async def ping(self):
            return False

        async def aclose(self):
            pass

    monkeypatch.setattr(cache.redis, "from_url", lambda *args, **kwargs: FakeRedis())

    assert await cache.get_client() is None
    assert await cache.redis_status() == "unavailable"
    assert isinstance(cache.redis_last_error(), str)
    assert "Redis ping failed" in cache.redis_last_error()


async def test_redis_exception_falls_back_to_memory(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid:6379")
    get_settings.cache_clear()

    class FakeRedis:
        async def ping(self):
            raise RedisError("connection refused")

        async def aclose(self):
            pass

    monkeypatch.setattr(cache.redis, "from_url", lambda *args, **kwargs: FakeRedis())

    await cache.set_cached("fallback", {"ok": True}, ttl=60)

    assert await cache.get_cached("fallback") == {"ok": True}
    assert await cache.redis_status() == "unavailable"
