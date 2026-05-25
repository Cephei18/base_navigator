from __future__ import annotations

import pytest

import cache
import rate_limit
from config import get_settings


@pytest.fixture(autouse=True)
def reset_runtime_state(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    cache._client = None
    cache._redis_failed = False
    cache._redis_retry_after = 0.0
    cache._redis_last_error = None
    cache._logged_no_redis = False
    cache._memory_cache.clear()
    cache._memory_values.clear()
    rate_limit.reset_memory_rate_limits()

    if request.node.get_closest_marker("integration"):
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()
        return

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("ENABLE_X402", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_PUBLIC_REQUESTS", "120")
    monkeypatch.setenv("RATE_LIMIT_PUBLIC_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_REFRESH_REQUESTS", "10")
    monkeypatch.setenv("RATE_LIMIT_REFRESH_WINDOW_SECONDS", "60")
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()
