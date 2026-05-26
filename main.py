from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cache import cache_backend_name, close_cache, get_client
from config import get_settings
from errors import register_error_handlers
from monitors.poller import start_polling_scheduler, stop_polling_scheduler
from observability import RequestContextMiddleware, configure_logging
from payments import install_payment_middleware
from rate_limit import RateLimitMiddleware
from routers import governance, grants, health

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Application startup beginning.", extra={"environment": settings.environment})
    await get_client()
    app.state.polling_scheduler = start_polling_scheduler()
    logger.info(
        "Application startup complete.",
        extra={"cache_backend": await cache_backend_name()},
    )
    yield
    logger.info("Application shutdown beginning.")
    stop_polling_scheduler(getattr(app.state, "polling_scheduler", None))
    await close_cache()
    logger.info("Application shutdown complete.")


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

install_payment_middleware(app, settings)

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)

if not settings.allowed_origins:
    logger.warning("No CORS origins configured; browser cross-origin access is disabled.")

register_error_handlers(app, settings)

app.include_router(governance.router, prefix="/api")
app.include_router(grants.router, prefix="/api")
app.include_router(health.router)
