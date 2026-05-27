from __future__ import annotations

from datetime import UTC, datetime

import cache
from signals import reasoner


def _signal(**overrides):
    signal = {
        "event_id": "signal-1",
        "event_type": "proposal_changed",
        "source": "snapshot",
        "protocol": "Base DAO",
        "title": "Allocate $2M to Base builders",
        "source_url": "https://example.com",
        "severity": "high",
        "urgency_score": 82,
        "importance_score": 52,
        "reasons": ["treasury impact above $1M", "deadline is under 6 hours away"],
        "score_components": [],
        "requires_llm_reasoning": True,
        "notify_users": False,
        "store_as_major_signal": True,
        "escalation_recommendation": "priority_digest",
        "raw_event": {
            "current": {
                "hours_until_deadline": 5,
                "estimated_treasury_impact_usd": 2_000_000,
            }
        },
    }
    signal.update(overrides)
    return signal


def _gemini_output(**overrides):
    output = {
        "ecosystem_summary": "Base DAO funding vote shifted sharply.",
        "why_this_matters": "The vote controls $2M of builder funding and is close to deadline.",
        "potential_impact": "Builders may see funding availability change this week.",
        "recommended_attention": "Base builders and governance operators should monitor turnout.",
        "confidence": 0.82,
        "risk_level": "high",
        "key_entities": ["Base DAO"],
        "follow_up_watch_items": ["Watch quorum and final vote distribution."],
    }
    output.update(overrides)
    return output


async def test_enrichment_skips_medium_signal_without_calling_gemini(monkeypatch):
    async def fail_call(*args, **kwargs):
        raise AssertionError("Gemini should not be called for medium signals")

    monkeypatch.setattr(reasoner, "call_gemini_json", fail_call)

    enriched = await reasoner.enrich_signal(
        _signal(severity="medium", urgency_score=42, requires_llm_reasoning=False)
    )

    assert "llm_enrichment" not in enriched
    assert await cache.get_counter("stats:gemini_enrichments_skipped") == 1


async def test_enrichment_attaches_structured_gemini_output_and_uses_cache(monkeypatch):
    calls = 0

    async def fake_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _gemini_output()

    monkeypatch.setattr(reasoner, "call_gemini_json", fake_call)
    signal = _signal(event_id="cached-signal")

    first = await reasoner.enrich_signal(signal)
    second = await reasoner.enrich_signal(signal)

    assert calls == 1
    assert first["llm_enrichment"]["status"] == "analyzed"
    assert first["llm_enrichment"]["ecosystem_summary"] == "Base DAO funding vote shifted sharply."
    assert second["llm_enrichment"]["cache_hit"] is True
    assert await cache.get_counter("stats:gemini_enrichments") == 1
    assert await cache.get_counter("stats:gemini_enrichment_cache_hits") == 1


async def test_enrichment_retries_before_success(monkeypatch):
    calls = 0

    async def flaky_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary model failure")
        return _gemini_output(risk_level="critical", confidence=91)

    monkeypatch.setattr(reasoner, "call_gemini_json", flaky_call)

    enriched = await reasoner.enrich_signal(_signal(event_id="retry-signal", severity="critical"))

    assert calls == 2
    assert enriched["llm_enrichment"]["status"] == "analyzed"
    assert enriched["llm_enrichment"]["confidence"] == 0.91
    assert enriched["llm_enrichment"]["risk_level"] == "critical"


async def test_malformed_gemini_output_falls_back_without_losing_signal(monkeypatch):
    async def malformed_call(*args, **kwargs):
        return {"ecosystem_summary": ""}

    monkeypatch.setattr(reasoner, "call_gemini_json", malformed_call)

    enriched = await reasoner.enrich_signal(_signal(event_id="malformed-signal"))

    assert enriched["event_id"] == "malformed-signal"
    assert enriched["llm_enrichment"]["status"] == "failed"
    assert "Gemini enrichment failed after retries" in enriched["llm_enrichment"]["fallback_reason"]
    assert await cache.get_counter("stats:gemini_failures") == 1
    assert await cache.get_counter("stats:gemini_fallbacks") == 1
    today = datetime.now(UTC).date().isoformat()
    assert await cache.get_counter(f"stats:gemini_calls:{today}") == 2


async def test_daily_cap_marks_signal_unanalyzed_without_calling_gemini(monkeypatch):
    today = datetime.now(UTC).date().isoformat()
    await cache.increment_counter(
        f"stats:gemini_calls:{today}",
        amount=reasoner.DAILY_GEMINI_CAP,
    )

    async def fail_call(*args, **kwargs):
        raise AssertionError("Gemini should not be called after the daily cap")

    monkeypatch.setattr(reasoner, "call_gemini_json", fail_call)

    enriched = await reasoner.enrich_signal(_signal(event_id="capped-signal"))

    assert enriched["llm_enrichment"]["status"] == "skipped"
    assert enriched["llm_enrichment"]["fallback_reason"] == "daily_cap_reached"
    assert await cache.get_counter("stats:gemini_enrichments_skipped") == 1
    assert await cache.get_counter(f"stats:gemini_calls:{today}") == reasoner.DAILY_GEMINI_CAP


async def test_reason_about_signal_compatibility_wrapper(monkeypatch):
    async def fake_call(*args, **kwargs):
        return _gemini_output()

    monkeypatch.setattr(reasoner, "call_gemini_json", fake_call)

    enrichment = await reasoner.reason_about_signal(
        {
            "event_id": "wrapper-signal",
            "event_type": "proposal_changed",
            "source": "snapshot",
            "protocol": "Base DAO",
            "title": "Treasury vote",
        },
        75,
    )

    assert enrichment["status"] == "analyzed"


def test_escalated_social_signal_is_eligible_for_enrichment():
    assert reasoner.should_enrich_signal(
        {
            "source": "farcaster",
            "severity": "medium",
            "urgency_score": 48,
            "requires_llm_reasoning": True,
            "escalation_recommendation": "immediate_alert",
        }
    )
