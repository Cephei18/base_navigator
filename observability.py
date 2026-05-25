from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time
import traceback
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from cache import increment_counter

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)
_route: contextvars.ContextVar[str | None] = contextvars.ContextVar("route", default=None)

_RESERVED_LOG_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


def get_request_id() -> str | None:
    return _request_id.get()


def get_route() -> str | None:
    return _route.get()


def make_request_id() -> str:
    return uuid.uuid4().hex


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", None) or get_request_id(),
            "route": getattr(record, "route", None) or get_route(),
            "subsystem": getattr(record, "subsystem", record.name),
            "message": record.getMessage(),
            "logger": record.name,
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_ATTRS or key.startswith("_") or key in payload:
                continue
            payload[key] = value

        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            payload["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value),
                "stack_trace": "".join(traceback.format_exception(*record.exc_info)),
            }
            if "error" not in payload:
                payload["error"] = str(exc_value)

        return json.dumps(payload, default=str, ensure_ascii=True)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or make_request_id()
        route = request.url.path
        token_request_id = _request_id.set(request_id)
        token_route = _route.set(route)
        request.state.request_id = request_id

        logger = logging.getLogger("http")
        started_at = time.perf_counter()
        status_code = 500
        try:
            logger.info(
                "Request started.",
                extra={
                    "subsystem": "http",
                    "method": request.method,
                    "client_ip": client_ip(request),
                },
            )
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            try:
                await increment_counter("stats:http_requests_total")
            except Exception as exc:
                logger.warning(
                    "Request counter update failed.",
                    extra={"subsystem": "http", "error": f"{type(exc).__name__}: {exc}"},
                )
            logger.info(
                "Request completed.",
                extra={
                    "subsystem": "http",
                    "method": request.method,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip(request),
                },
            )
            _request_id.reset(token_request_id)
            _route.reset(token_route)


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    trust_proxy = os.getenv("TRUST_PROXY_HEADERS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if trust_proxy and forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"
