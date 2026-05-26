from __future__ import annotations

from datetime import UTC, datetime

from signals.scorer import build_signal, classify_severity, score_event


def _event(**overrides):
    event = {
        "event_id": "event-1",
        "event_type": "proposal_changed",
        "source": "snapshot",
        "protocol": "Example DAO",
        "title": "Treasury vote",
        "source_url": "https://example.com",
        "vote_swing_pct": 0,
        "hours_until_deadline": 999_999,
        "estimated_treasury_impact_usd": 0,
        "is_new_proposal": False,
        "quorum_at_risk": False,
        "for_vs_against_swing": False,
    }
    event.update(overrides)
    return event


def test_score_event_applies_weighted_threshold_rules_exclusively():
    assert score_event(_event(vote_swing_pct=21)) == 30
    assert score_event(_event(vote_swing_pct=11)) == 15
    assert score_event(_event(hours_until_deadline=5)) == 25
    assert score_event(_event(hours_until_deadline=23)) == 15
    assert score_event(_event(hours_until_deadline=71)) == 8
    assert score_event(_event(estimated_treasury_impact_usd=1_000_001)) == 40
    assert score_event(_event(estimated_treasury_impact_usd=100_001)) == 20


def test_build_signal_explains_critical_governance_event():
    signal = build_signal(
        _event(
            vote_swing_pct=25,
            hours_until_deadline=5,
            estimated_treasury_impact_usd=2_000_000,
            is_new_proposal=True,
            quorum_at_risk=True,
            for_vs_against_swing=True,
        ),
        now=datetime(2026, 5, 26, tzinfo=UTC),
    )

    assert signal.urgency_score == 160
    assert signal.importance_score == 50
    assert signal.severity == "critical"
    assert signal.requires_llm_reasoning is True
    assert signal.notify_users is True
    assert signal.store_as_major_signal is True
    assert "for/against result flipped since last check" in signal.reasons


def test_severity_classification_boundaries_are_stable():
    assert classify_severity(29) == "low"
    assert classify_severity(30) == "medium"
    assert classify_severity(50) == "high"
    assert classify_severity(70) == "critical"


def test_base_native_grant_relevance_is_scored_but_not_over_escalated():
    signal = build_signal(
        _event(
            event_type="grant_new",
            source="base_batches",
            protocol="Base",
            title="Base Batches 2026",
            is_new_grant=True,
        )
    )

    assert signal.urgency_score == 20
    assert signal.importance_score == 20
    assert signal.severity == "low"
    assert signal.requires_llm_reasoning is False
    assert "Base-native ecosystem relevance" in signal.reasons
