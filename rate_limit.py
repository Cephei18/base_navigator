from __future__ import annotations

import hmac
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from cache import get_client, increment_counter, mark_redis_unavailable, redis_status
from config import Settings, get_settings
from observability import REQUEST_ID_HEADER, client_ip, get_request_id

logger = logging.getLogger(__name__)

_memory_windows: dict[str, tuple[float, int]] = {}


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_after: int
    backend: Literal["redis", "memory", "disabled"]
    bucket: Literal["public", "refresh"]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled or _has_internal_key(request, settings):
            response = await call_next(request)
            response.headers["X-RateLimit-Backend"] = "disabled"
            return response

        decision = await check_rate_limit(request, settings)
        if not decision.allowed:
            request_id = get_request_id() or getattr(request.state, "request_id", "unknown")
            await increment_counter("stats:http_rate_limited_total")
            logger.warning(
                "Rate limit exceeded.",
                extra={
                    "subsystem": "rate_limit",
                    "client_ip": client_ip(request),
                    "bucket": decision.bucket,
                    "limit": decision.limit,
                    "retry_after_seconds": decision.retry_after,
                    "backend": decision.backend,
                },
            )
            return JSONResponse(
                status_code=429,
                headers={
                    REQUEST_ID_HEADER: request_id,
                    "Retry-After": str(decision.retry_after),
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(decision.reset_after),
                    "X-RateLimit-Backend": decision.backend,
                },
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Rate limit exceeded.",
                        "request_id": request_id,
                        "retry_after_seconds": decision.retry_after,
                    }
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(decision.reset_after)
        response.headers["X-RateLimit-Backend"] = decision.backend
        return response


async def check_rate_limit(request: Request, settings: Settings) -> RateLimitDecision:
    bucket = "refresh" if _is_refresh_request(request) else "public"
    limit = (
        settings.rate_limit_refresh_requests
        if bucket == "refresh"
        else settings.rate_limit_public_requests
    )
    window = (
        settings.rate_limit_refresh_window_seconds
        if bucket == "refresh"
        else settings.rate_limit_public_window_seconds
    )
    ip = client_ip(request)
    now = time.time()
    window_id = int(now // window)
    key = f"rate_limit:{bucket}:{ip}:{window_id}"
    reset_at = int((window_id + 1) * window)
    reset_after = max(1, reset_at - int(now))

    client = await get_client()
    if client is not None:
        try:
            count = int(await client.incr(key))
            if count == 1:
                await client.expire(key, window + 1)
            return _decision(count, limit, reset_after, "redis", bucket)
        except RedisError as exc:
            await mark_redis_unavailable(exc)
            logger.warning(
                "Rate limiter Redis command failed; using memory fallback.",
                extra={"subsystem": "rate_limit", "error": f"{type(exc).__name__}: {exc}"},
            )

    count = _memory_increment(key, now, window)
    return _decision(count, limit, reset_after, "memory", bucket)


async def rate_limit_backend_status(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not settings.rate_limit_enabled:
        return "disabled"
    return "redis" if await redis_status() == "connected" else "memory"


def reset_memory_rate_limits() -> None:
    _memory_windows.clear()


def _decision(
    count: int,
    limit: int,
    reset_after: int,
    backend: Literal["redis", "memory"],
    bucket: Literal["public", "refresh"],
) -> RateLimitDecision:
    remaining = max(0, limit - count)
    return RateLimitDecision(
        allowed=count <= limit,
        limit=limit,
        remaining=remaining,
        retry_after=reset_after,
        reset_after=reset_after,
        backend=backend,
        bucket=bucket,
    )


def _memory_increment(key: str, now: float, window: int) -> int:
    expires_at, count = _memory_windows.get(key, (now + window, 0))
    if expires_at <= now:
        expires_at = now + window
        count = 0
    count += 1
    _memory_windows[key] = (expires_at, count)
    return count


def _is_refresh_request(request: Request) -> bool:
    return request.query_params.get("refresh", "").strip().lower() in {"1", "true", "yes", "on"}


def _has_internal_key(request: Request, settings: Settings) -> bool:
    if not settings.internal_key:
        return False
    supplied = request.headers.get("x-internal-key")
    return bool(supplied and hmac.compare_digest(supplied, settings.internal_key))
