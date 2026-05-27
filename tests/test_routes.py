from __future__ import annotations

import cache
from config import get_settings
from routers import governance as governance_router
from routers import grants as grants_router
from signals import store


def _signal(**overrides):
    signal = {
        "event_id": "signal-1",
        "event_type": "proposal_changed",
        "source": "snapshot",
        "protocol": "Base DAO",
        "title": "Treasury vote",
        "severity": "high",
        "urgency_score": 60,
        "importance_score": 20,
        "reasons": ["vote swing above 20%"],
        "created_at": "2026-05-26T00:00:00+00:00",
    }
    signal.update(overrides)
    return signal


async def test_governance_route_serves_precomputed_signals():
    await store.save_signal(_signal(event_id="gov-1"))

    response = await governance_router.governance_intelligence()

    assert response.source == "precomputed"
    assert response.category == "governance"
    assert response.signals_count == 1
    assert response.signals[0]["event_id"] == "gov-1"
    assert await cache.get_counter("stats:queries_served") == 1


async def test_governance_route_quiet_period_does_not_live_fetch(monkeypatch):
    async def fail_fetch():
        raise AssertionError("live fetch should be disabled by default")

    monkeypatch.setattr(governance_router, "fetch_active_proposals", fail_fetch)

    response = await governance_router.governance_intelligence(refresh=True)

    assert response.source == "precomputed"
    assert response.quiet_period is True
    assert response.message == "No high-priority ecosystem signals detected."


async def test_governance_route_uses_live_fallback_only_when_enabled(monkeypatch):
    monkeypatch.setenv("ALLOW_LIVE_FALLBACK", "true")
    get_settings.cache_clear()

    async def fake_fetch_active_proposals():
        return [{"id": "proposal-1"}]

    async def fake_synthesize_governance(proposals):
        assert proposals == [{"id": "proposal-1"}]
        return {
            "as_of": "2026-05-24T00:00:00+00:00",
            "active_proposals": [
                {
                    "protocol": "Base DAO",
                    "title": "Fund public goods",
                    "tldr": "Funds useful builders.",
                    "voting_ends": "2026-05-25T00:00:00+00:00",
                    "hours_remaining": 24,
                    "current_result": "passing",
                    "for_pct": 60.0,
                    "impact": "medium",
                    "source_url": "https://snapshot.box/#/proposal/1",
                    "urgency": "high",
                }
            ],
            "urgent_count": 1,
            "summary_for_agents": "One active governance proposal needs attention.",
        }

    monkeypatch.setattr(governance_router, "fetch_active_proposals", fake_fetch_active_proposals)
    monkeypatch.setattr(governance_router, "synthesize_governance", fake_synthesize_governance)

    response = await governance_router.governance_intelligence(refresh=True)

    assert response.source == "live_fallback"
    assert response.live_fallback["urgent_count"] == 1
    assert await cache.get_cached("cache:governance:v1") is not None
    assert await cache.get_counter("stats:queries_served") == 1


async def test_grants_route_serves_precomputed_signals():
    await store.save_signal(
        _signal(
            event_id="grant-1",
            event_type="grant_changed",
            source="gitcoin",
            protocol="Gitcoin",
            title="Base builder grants round",
        )
    )

    response = await grants_router.grants_intelligence()

    assert response.source == "precomputed"
    assert response.category == "grants"
    assert response.signals_count == 1
    assert response.signals[0]["event_id"] == "grant-1"


async def test_grants_route_uses_live_fallback_only_when_enabled(monkeypatch):
    monkeypatch.setenv("ALLOW_LIVE_FALLBACK", "true")
    get_settings.cache_clear()

    async def fake_fetch_active_grants():
        return [{"id": "grant-1"}]

    async def fake_synthesize_grants(grants):
        assert grants == [{"id": "grant-1"}]
        grant = {
            "name": "Base Builders Round",
            "operator": "Base",
            "amount": "10000 USDC",
            "deadline": "2026-05-25T00:00:00+00:00",
            "urgency": "high",
            "eligibility": ["Build on Base"],
            "apply_url": "https://example.com/apply",
            "tldr": "Funding for Base builders.",
        }
        return {
            "as_of": "2026-05-24T00:00:00+00:00",
            "open_grants": [grant],
            "urgent_deadlines": [grant],
            "pro_tip": "Apply before the deadline.",
        }

    monkeypatch.setattr(grants_router, "fetch_active_grants", fake_fetch_active_grants)
    monkeypatch.setattr(grants_router, "synthesize_grants", fake_synthesize_grants)

    response = await grants_router.grants_intelligence(refresh=True)

    assert response.source == "live_fallback"
    assert response.live_fallback["open_grants"][0]["name"] == "Base Builders Round"
    assert await cache.get_cached("cache:grants:v1") is not None
    assert await cache.get_counter("stats:queries_served") == 1
