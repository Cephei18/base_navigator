from __future__ import annotations

import cache
from routers import governance as governance_router
from routers import grants as grants_router


async def test_governance_route_generates_valid_response_and_updates_cache(monkeypatch):
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

    assert response.urgent_count == 1
    assert await cache.get_cached("governance:base:v1") is not None
    assert await cache.get_counter("stats:queries_served") == 1


async def test_grants_route_generates_valid_response_and_updates_cache(monkeypatch):
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

    assert response.open_grants[0].name == "Base Builders Round"
    assert await cache.get_cached("grants:base:v1") is not None
    assert await cache.get_counter("stats:queries_served") == 1
