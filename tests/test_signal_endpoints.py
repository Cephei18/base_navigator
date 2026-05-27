from __future__ import annotations

import cache
from routers import signals as signals_router
from routers import social as social_router
from signals import store


def _signal(**overrides):
    signal = {
        "event_id": "signal-1",
        "event_type": "proposal_changed",
        "source": "snapshot",
        "protocol": "Base DAO",
        "title": "Treasury vote",
        "severity": "critical",
        "urgency_score": 82,
        "importance_score": 40,
        "reasons": ["treasury impact above $1M"],
        "score_components": [{"rule": "treasury_impact_gt_1m", "points": 40}],
        "raw_event": {"current": {"estimated_treasury_impact_usd": 2_000_000}},
        "llm_enrichment": {
            "status": "analyzed",
            "ecosystem_summary": "Base DAO funding vote shifted sharply.",
        },
        "created_at": "2026-05-26T00:00:00+00:00",
    }
    signal.update(overrides)
    return signal


async def test_public_signals_endpoint_returns_public_feed_without_raw_event():
    await store.save_signal(_signal())

    response = await signals_router.signal_feed()

    assert response.source == "precomputed"
    assert response.signals_count == 1
    assert response.quiet_period is False
    assert response.signals[0]["llm_enrichment"]["status"] == "analyzed"
    assert "raw_event" not in response.signals[0]
    assert "score_components" not in response.signals[0]
    assert await cache.get_counter("stats:signals_public_reads") == 1


async def test_premium_signals_endpoint_returns_full_signal_payload():
    await store.save_signal(_signal())

    response = await signals_router.premium_signal_feed()

    assert response.premium is True
    assert response.signals_count == 1
    assert response.signals[0]["raw_event"]["current"]["estimated_treasury_impact_usd"] == 2_000_000
    assert response.signals[0]["score_components"][0]["rule"] == "treasury_impact_gt_1m"
    assert await cache.get_counter("stats:signals_premium_reads") == 1
    assert await cache.get_counter("stats:queries_served") == 1


async def test_public_signals_endpoint_handles_quiet_period():
    response = await signals_router.signal_feed()

    assert response.quiet_period is True
    assert response.signals == []
    assert response.message == "No high-priority ecosystem signals detected."


async def test_social_signals_endpoint_returns_quiet_period_when_empty():
    response = await social_router.social_signal_feed()

    assert response.category == "social"
    assert response.quiet_period is True
    assert response.signals == []
