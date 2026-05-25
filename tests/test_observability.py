from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from config import get_settings
from errors import register_error_handlers
from observability import REQUEST_ID_HEADER, RequestContextMiddleware, get_request_id
from rate_limit import RateLimitMiddleware


def _test_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app, settings)

    @app.get("/ok")
    async def ok():
        return {"request_id": get_request_id()}

    @app.get("/explode")
    async def explode():
        raise RuntimeError("sensitive failure detail")

    return app


async def test_request_id_is_generated_and_returned():
    transport = ASGITransport(app=_test_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/ok")

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]


async def test_incoming_request_id_is_preserved():
    transport = ASGITransport(app=_test_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/ok", headers={REQUEST_ID_HEADER: "trace-123"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "trace-123"
    assert response.json()["request_id"] == "trace-123"


async def test_rate_limit_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PUBLIC_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_PUBLIC_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    transport = ASGITransport(app=_test_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/ok")
        second = await client.get("/ok")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    assert second.headers[REQUEST_ID_HEADER]
    assert second.json()["error"]["code"] == "rate_limited"


async def test_refresh_requests_use_refresh_rate_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PUBLIC_REQUESTS", "100")
    monkeypatch.setenv("RATE_LIMIT_REFRESH_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_REFRESH_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    transport = ASGITransport(app=_test_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.get("/ok?refresh=true")
        second = await client.get("/ok?refresh=true")

    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "1"
    assert second.status_code == 429


async def test_unhandled_errors_include_request_id_and_safe_message(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    transport = ASGITransport(app=_test_app(), raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/explode", headers={REQUEST_ID_HEADER: "error-trace"})

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "error-trace"
    body = response.json()
    assert body["error"]["request_id"] == "error-trace"
    assert body["error"]["message"] == "Internal server error."
    assert "details" not in body["error"]
