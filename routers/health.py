from __future__ import annotations

from datetime import UTC, datetime
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
from monitors.poller import polling_scheduler_status
from rate_limit import rate_limit_backend_status
from signals.reasoner import DAILY_GEMINI_CAP, average_enrichment_latency_ms
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
    today = datetime.now(UTC).date().isoformat()
    scheduler_status = polling_scheduler_status()
    signal_store_size = await get_signal_store_size()
    last_snapshot_success_at = await get_value("stats:last_snapshot_success_at")
    last_gitcoin_success_at = await get_value("stats:last_gitcoin_success_at")
    snapshot_data_stale = _is_stale(last_snapshot_success_at, settings.source_stale_hours)
    gitcoin_data_stale = _is_stale(last_gitcoin_success_at, settings.source_stale_hours)
    stale_source_warnings = []
    if snapshot_data_stale:
        stale_source_warnings.append("snapshot_data_stale")
    if gitcoin_data_stale:
        stale_source_warnings.append("gitcoin_data_stale")
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
        last_poll_time=await get_value("stats:last_poll_time"),
        next_poll_time=scheduler_status["next_poll_time"],
        scheduler_running=scheduler_status["scheduler_running"],
        total_signals_generated=await get_counter("stats:signals_generated"),
        high_severity_signals=await get_counter("stats:signals_high_severity"),
        ignored_events_count=await get_counter("stats:signals_ignored"),
        escalated_events_count=await get_counter("stats:signals_escalated"),
        signals_in_store=signal_store_size,
        signals_in_feed=signal_store_size,
        scoring_engine_health=await get_value("stats:scoring_engine_health") or "unknown",
        total_gemini_enrichments=await get_counter("stats:gemini_enrichments"),
        gemini_enrichments_skipped=await get_counter("stats:gemini_enrichments_skipped"),
        gemini_enrichment_cache_hits=await get_counter("stats:gemini_enrichment_cache_hits"),
        gemini_enrichment_cache_misses=await get_counter("stats:gemini_enrichment_cache_misses"),
        gemini_failures=await get_counter("stats:gemini_failures"),
        gemini_fallbacks=await get_counter("stats:gemini_fallbacks"),
        gemini_calls_today=await get_counter(f"stats:gemini_calls:{today}"),
        gemini_daily_cap=DAILY_GEMINI_CAP,
        average_gemini_enrichment_latency_ms=await average_enrichment_latency_ms(),
        last_successful_enrichment=await get_value("stats:last_gemini_enrichment_at"),
        last_snapshot_success_at=last_snapshot_success_at,
        last_snapshot_non_empty_at=await get_value("stats:last_snapshot_non_empty_at"),
        last_snapshot_failure_at=await get_value("stats:last_snapshot_failure_at"),
        last_gitcoin_success_at=last_gitcoin_success_at,
        last_gitcoin_non_empty_at=await get_value("stats:last_gitcoin_non_empty_at"),
        last_gitcoin_failure_at=await get_value("stats:last_gitcoin_failure_at"),
        snapshot_data_stale=snapshot_data_stale,
        gitcoin_data_stale=gitcoin_data_stale,
        stale_source_warnings=stale_source_warnings,
    )


def _is_stale(value: object, threshold_hours: int) -> bool:
    if not isinstance(value, str) or not value:
        return True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (datetime.now(UTC) - parsed).total_seconds() > threshold_hours * 3600
