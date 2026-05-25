from __future__ import annotations

from datetime import UTC, datetime, timedelta

from synthesis import governance as governance_synthesis
from synthesis import grants as grants_synthesis


async def test_governance_synthesis_uses_deterministic_fallback(monkeypatch):
    async def fail_gemini(*args, **kwargs):
        raise RuntimeError("gemini unavailable")

    monkeypatch.setattr(governance_synthesis, "call_gemini_json", fail_gemini)
    voting_end = int((datetime.now(UTC) + timedelta(hours=12)).timestamp())

    result = await governance_synthesis.synthesize_governance(
        [
            {
                "id": "proposal-1",
                "title": "Fund Base public goods",
                "body": "Allocate funding to Base ecosystem public goods builders.",
                "space": {"id": "basedao.eth", "name": "Base DAO"},
                "end": voting_end,
                "scores": [60, 40],
                "scores_total": 100,
            }
        ]
    )

    assert result["urgent_count"] == 1
    assert result["active_proposals"][0]["current_result"] == "passing"
    assert result["active_proposals"][0]["urgency"] == "high"


async def test_grants_synthesis_uses_deterministic_fallback(monkeypatch):
    async def fail_gemini(*args, **kwargs):
        raise RuntimeError("gemini unavailable")

    monkeypatch.setattr(grants_synthesis, "call_gemini_json", fail_gemini)
    deadline = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    result = await grants_synthesis.synthesize_grants(
        [
            {
                "source": "gitcoin",
                "roundMetadata": {
                    "name": "Base Builders Round",
                    "description": "Funding for useful Base applications.",
                    "applicationUrl": "https://example.com/apply",
                    "eligibility": ["Build on Base"],
                },
                "applicationsEndTime": deadline,
                "matchingFundsAvailable": "10000 USDC",
            }
        ]
    )

    assert result["open_grants"][0]["name"] == "Base Builders Round"
    assert result["urgent_deadlines"][0]["urgency"] == "high"
