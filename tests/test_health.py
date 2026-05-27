from __future__ import annotations

from datetime import UTC, datetime, timedelta

import cache
from routers.health import health


async def test_health_reports_degraded_memory_mode_and_estimated_revenue():
    await cache.increment_counter("stats:queries_served", amount=3)

    response = await health()

    assert response.cache_backend == "memory"
    assert response.redis_status == "not_configured"
    assert response.gemini_configured is False
    assert response.degraded_mode is True
    assert "redis_not_configured" in response.degraded_reasons
    assert "gemini_not_configured" in response.degraded_reasons
    assert response.total_usdc_earned_estimated == "0.03"
    assert response.verified_usdc_earned is None
    assert response.revenue_basis == "estimated_from_queries"
    assert response.total_signals_generated == 0
    assert response.ignored_events_count == 0
    assert response.scoring_engine_health == "unknown"
    assert response.total_gemini_enrichments == 0
    assert response.gemini_daily_cap == 50
    assert response.average_gemini_enrichment_latency_ms == 0
    assert response.scheduler_running is False
    assert response.last_poll_time is None
    assert response.signals_in_feed == 0
    assert response.snapshot_data_stale is True
    assert response.gitcoin_data_stale is True


async def test_health_reports_source_freshness_and_staleness():
    now = datetime.now(UTC)
    await cache.set_value("stats:last_snapshot_success_at", (now - timedelta(hours=25)).isoformat())
    await cache.set_value("stats:last_gitcoin_success_at", now.isoformat())
    await cache.set_value("stats:last_poll_time", now.isoformat())

    response = await health()

    assert response.last_poll_time == now.isoformat()
    assert response.snapshot_data_stale is True
    assert response.gitcoin_data_stale is False
    assert "snapshot_data_stale" in response.stale_source_warnings
