from __future__ import annotations

import json
import logging
import time
from inspect import isawaitable
from typing import Any, Literal

import redis.asyncio as redis
from redis.exceptions import RedisError

from config import get_settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_redis_failed = False
_redis_retry_after = 0.0
_redis_last_error: str | None = None
_logged_no_redis = False
_memory_cache: dict[str, tuple[float, Any]] = {}
_memory_values: dict[str, Any] = {}
_started_at = time.time()
_REDIS_RETRY_SECONDS = 30


async def get_client() -> redis.Redis | None:
    global _client, _logged_no_redis, _redis_failed, _redis_last_error
    settings = get_settings()
    if not settings.redis_url:
        if not _logged_no_redis:
            logger.info("REDIS_URL is not configured; using in-memory cache.")
            _logged_no_redis = True
        return None
    if _redis_failed and time.time() < _redis_retry_after:
        return None
    if _client is None:
        client: redis.Redis | None = None
        try:
            logger.info("Connecting to Redis cache.")
            client = redis.from_url(settings.redis_url, decode_responses=True)
            if not await _ping_redis(client):
                raise RedisError("Redis ping failed.")
        except RedisError as exc:
            if client is not None:
                await _close_redis_client(client)
            _mark_redis_failed(exc)
            return None
        _client = client
        _redis_failed = False
        _redis_last_error = None
        logger.info("Redis cache connected.")
    return _client


async def close_cache() -> None:
    global _client
    if _client is not None:
        await _close_redis_client(_client)
        _client = None


async def get_cached(key: str) -> Any | None:
    client = await get_client()
    if client is not None:
        try:
            value = await client.get(key)
            if not value:
                logger.debug("Cache miss.", extra={"cache_key": key, "cache_backend": "redis"})
                return None
            logger.debug("Cache hit.", extra={"cache_key": key, "cache_backend": "redis"})
            return json.loads(value)
        except RedisError as exc:
            await _handle_redis_error(exc)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Ignoring invalid JSON in Redis cache.",
                extra={"cache_key": key, "error": str(exc)},
            )
            return None

    item = _memory_cache.get(key)
    if item is None:
        logger.debug("Cache miss.", extra={"cache_key": key, "cache_backend": "memory"})
        return None
    expires_at, value = item
    if expires_at < time.time():
        _memory_cache.pop(key, None)
        logger.debug("Cache expired.", extra={"cache_key": key, "cache_backend": "memory"})
        return None
    logger.debug("Cache hit.", extra={"cache_key": key, "cache_backend": "memory"})
    return value


async def set_cached(key: str, value: Any, ttl: int) -> None:
    client = await get_client()
    if client is not None:
        try:
            await client.setex(key, ttl, json.dumps(value))
            logger.debug(
                "Cache write.",
                extra={"cache_key": key, "cache_backend": "redis", "ttl": ttl},
            )
            return
        except RedisError as exc:
            await _handle_redis_error(exc)
    _memory_cache[key] = (time.time() + ttl, value)
    logger.debug("Cache write.", extra={"cache_key": key, "cache_backend": "memory", "ttl": ttl})


async def increment_counter(key: str, amount: int = 1) -> int:
    client = await get_client()
    if client is not None:
        try:
            return int(await client.incrby(key, amount))
        except RedisError as exc:
            await _handle_redis_error(exc)

    current = int(_memory_values.get(key, 0)) + amount
    _memory_values[key] = current
    return current


async def get_counter(key: str) -> int:
    client = await get_client()
    if client is not None:
        try:
            value = await client.get(key)
            return int(value or 0)
        except RedisError as exc:
            await _handle_redis_error(exc)
    return int(_memory_values.get(key, 0))


async def set_value(key: str, value: Any) -> None:
    client = await get_client()
    if client is not None:
        try:
            await client.set(key, json.dumps(value))
            return
        except RedisError as exc:
            await _handle_redis_error(exc)
    _memory_values[key] = value


async def get_value(key: str) -> Any | None:
    client = await get_client()
    if client is not None:
        try:
            value = await client.get(key)
            return json.loads(value) if value else None
        except RedisError as exc:
            await _handle_redis_error(exc)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Ignoring invalid JSON value in Redis.",
                extra={"cache_key": key, "error": str(exc)},
            )
            return None
    return _memory_values.get(key)


async def cache_backend_name() -> str:
    return "redis" if await get_client() is not None else "memory"


async def redis_status() -> Literal["connected", "unavailable", "not_configured"]:
    settings = get_settings()
    if not settings.redis_url:
        return "not_configured"
    return "connected" if await get_client() is not None else "unavailable"


async def mark_redis_unavailable(exc: RedisError) -> None:
    await _handle_redis_error(exc)


def redis_last_error() -> str | None:
    return _redis_last_error


def uptime_seconds() -> int:
    return int(time.time() - _started_at)


def _mark_redis_failed(exc: RedisError) -> None:
    global _client, _redis_failed, _redis_last_error, _redis_retry_after
    _client = None
    _redis_failed = True
    _redis_retry_after = time.time() + _REDIS_RETRY_SECONDS
    _redis_last_error = f"{type(exc).__name__}: {exc}"
    logger.warning(
        "Redis unavailable; using in-memory cache.",
        extra={"redis_error": _redis_last_error, "redis_retry_seconds": _REDIS_RETRY_SECONDS},
    )


async def _handle_redis_error(exc: RedisError) -> None:
    client = _client
    if client is not None:
        await _close_redis_client(client)
    _mark_redis_failed(exc)


async def _close_redis_client(client: redis.Redis) -> None:
    try:
        await client.aclose()
    except RedisError as exc:
        logger.debug(
            "Redis close failed.",
            extra={"redis_error": f"{type(exc).__name__}: {exc}"},
        )


async def _ping_redis(client: redis.Redis) -> bool:
    ping_result: Any = client.ping()
    if isawaitable(ping_result):
        ping_result = await ping_result
    return bool(ping_result)
