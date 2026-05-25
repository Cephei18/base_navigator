from __future__ import annotations

import os
from dataclasses import replace

import pytest
import redis.asyncio as redis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from config import get_settings
from fetchers.snapshot import fetch_active_proposals
from payments import install_payment_middleware
from synthesis.common import call_gemini_json

pytestmark = pytest.mark.integration


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


async def test_live_redis_connectivity():
    settings = get_settings()
    if not _env_enabled("RUN_REDIS_INTEGRATION_TESTS") or not settings.redis_url:
        pytest.skip("RUN_REDIS_INTEGRATION_TESTS=true and REDIS_URL are required")
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        assert await client.ping() is True
    finally:
        await client.aclose()


async def test_live_gemini_json_call():
    settings = get_settings()
    if not _env_enabled("RUN_GEMINI_INTEGRATION_TESTS") or not settings.gemini_api_key:
        pytest.skip("RUN_GEMINI_INTEGRATION_TESTS=true and GEMINI_API_KEY are required")

    result = await call_gemini_json(
        "Return ONLY a valid JSON object exactly like {\"ok\": true}.",
        {"ping": "pong"},
        max_tokens=64,
    )

    assert isinstance(result, dict)


@pytest.mark.skipif(
    not _env_enabled("RUN_SNAPSHOT_INTEGRATION_TESTS"),
    reason="RUN_SNAPSHOT_INTEGRATION_TESTS=true is not configured",
)
async def test_live_snapshot_fetch():
    proposals = await fetch_active_proposals(first=1)

    assert isinstance(proposals, list)


@pytest.mark.skipif(
    not _env_enabled("RUN_X402_INTEGRATION_TESTS") or not os.getenv("WALLET_ADDRESS"),
    reason="RUN_X402_INTEGRATION_TESTS=true and WALLET_ADDRESS are required",
)
async def test_x402_protected_route_requires_payment():
    settings = replace(
        get_settings(),
        enable_x402=True,
        wallet_address=os.getenv("WALLET_ADDRESS"),
    )
    app = FastAPI()

    @app.post("/api/governance")
    async def protected_route():
        return {"ok": True}

    assert install_payment_middleware(app, settings) is True

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/governance")

    assert response.status_code == 402
