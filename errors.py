from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from config import Settings
from observability import REQUEST_ID_HEADER, get_request_id

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI, settings: Settings) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        request_id = _request_id(request)
        headers = dict(exc.headers or {})
        headers[REQUEST_ID_HEADER] = request_id
        logger.warning(
            "HTTP error response.",
            extra={
                "subsystem": "errors",
                "status_code": exc.status_code,
                "error": str(exc.detail),
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content=_error_payload(
                code="http_error",
                message=str(exc.detail),
                request_id=request_id,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = _request_id(request)
        logger.warning(
            "Request validation failed.",
            extra={"subsystem": "errors", "status_code": 422, "error": str(exc)},
        )
        return JSONResponse(
            status_code=422,
            headers={REQUEST_ID_HEADER: request_id},
            content=_error_payload(
                code="validation_error",
                message="Invalid request.",
                request_id=request_id,
                details=exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.exception(
            "Unhandled exception.",
            extra={"subsystem": "errors", "error": f"{type(exc).__name__}: {exc}"},
        )
        details: dict[str, Any] | None = None
        message = "Internal server error."
        if settings.environment not in {"production", "prod"}:
            message = f"{type(exc).__name__}: {exc}"
            details = {"stack_trace": traceback.format_exc()}
        return JSONResponse(
            status_code=500,
            headers={REQUEST_ID_HEADER: request_id},
            content=_error_payload(
                code="internal_server_error",
                message=message,
                request_id=request_id,
                details=details,
            ),
        )


def _request_id(request: Request) -> str:
    return get_request_id() or getattr(request.state, "request_id", "unknown")


def _error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    details: Any | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
    if details is not None:
        error["details"] = details
    return {"error": error}
