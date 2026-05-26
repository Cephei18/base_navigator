from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from cache import (
    cache_backend_name,
    get_counter,
    get_value,
    redis_last_error,
    redis_status,
    uptime_seconds,
)
from config import get_settings
from models import HealthResponse
from rate_limit import rate_limit_backend_status
from signals.store import get_signal_store_size

router = APIRouter(tags=["health"])


def _query_revenue(queries: int, price: str) -> str:
    numeric = price.replace("$", "").strip()
    try:
        return f"{Decimal(queries) * Decimal(numeric):.2f}"
    except Exception:
        return "0.00"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    query_count = await get_counter("stats:queries_served")
    http_request_count = await get_counter("stats:http_requests_total")
    rate_limited_count = await get_counter("stats:http_rate_limited_total")
    current_redis_status = await redis_status()
    current_rate_limit_backend = await rate_limit_backend_status(settings)
    degraded_reasons: list[str] = []
    degraded_subsystems: list[str] = []
    if current_redis_status != "connected":
        degraded_reasons.append(f"redis_{current_redis_status}")
        degraded_subsystems.append("redis")
    if settings.rate_limit_enabled and current_rate_limit_backend == "memory":
        degraded_reasons.append("rate_limit_memory_fallback")
        degraded_subsystems.append("rate_limit")
    if not settings.gemini_api_key:
        degraded_reasons.append("gemini_not_configured")
        degraded_subsystems.append("gemini")
    revenue_estimate = _query_revenue(query_count, settings.x402_price_usd)
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=uptime_seconds(),
        cache_backend=await cache_backend_name(),
        redis_status=current_redis_status,
        redis_last_error=redis_last_error(),
        rate_limit_enabled=settings.rate_limit_enabled,
        rate_limit_backend=current_rate_limit_backend,
        request_id_enabled=True,
        gemini_configured=bool(settings.gemini_api_key),
        degraded_mode=bool(degraded_reasons),
        degraded_reasons=degraded_reasons,
        degraded_subsystems=sorted(set(degraded_subsystems)),
        x402_enabled=settings.enable_x402 and bool(settings.wallet_address),
        total_http_requests=http_request_count,
        total_rate_limited_requests=rate_limited_count,
        total_queries_served=query_count,
        total_usdc_earned=revenue_estimate,
        total_usdc_earned_estimated=revenue_estimate,
        verified_usdc_earned=None,
        revenue_basis="estimated_from_queries",
        last_governance_update=await get_value("stats:last_governance_update"),
        last_grants_update=await get_value("stats:last_grants_update"),
        total_signals_generated=await get_counter("stats:signals_generated"),
        high_severity_signals=await get_counter("stats:signals_high_severity"),
        ignored_events_count=await get_counter("stats:signals_ignored"),
        escalated_events_count=await get_counter("stats:signals_escalated"),
        signals_in_store=await get_signal_store_size(),
        scoring_engine_health=await get_value("stats:scoring_engine_health") or "unknown",
    )
