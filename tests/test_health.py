from __future__ import annotations

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
