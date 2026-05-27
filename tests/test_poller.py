from __future__ import annotations

from datetime import UTC, datetime, timedelta

import cache
from monitors import poller
from signals import store


async def test_poll_ecosystem_stores_state_and_prioritized_signals(monkeypatch):
    proposal = {
        "id": "proposal-1",
        "title": "Fund Base public goods",
        "body": "Allocate $250k to builders.",
        "space": {"id": "base.eth", "name": "Base DAO"},
        "end": int((datetime.now(UTC) + timedelta(days=2)).timestamp()),
        "scores": [75, 25],
        "scores_total": 100,
        "votes": 10,
        "quorum": 150,
    }
    grant = {
        "source": "gitcoin",
        "id": "round-1",
        "roundMetadata": {"name": "Base Builders Round"},
        "applicationsEndTime": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        "matchingFundsAvailable": 50_000,
    }

    async def fake_fetch_active_proposals():
        return [proposal]

    async def fake_fetch_active_grants():
        return [grant]

    monkeypatch.setattr(poller, "fetch_active_proposals", fake_fetch_active_proposals)
    monkeypatch.setattr(poller, "fetch_active_grants", fake_fetch_active_grants)
    monkeypatch.setattr(poller, "snapshot_fetch_ok", lambda: True)
    monkeypatch.setattr(poller, "gitcoin_fetch_ok", lambda: True)

    signals = await poller.poll_ecosystem()

    assert await cache.get_value(poller.SNAPSHOT_STATE_KEY) == [proposal]
    assert await cache.get_value(poller.GITCOIN_STATE_KEY) == [grant]
    assert await cache.get_value("stats:last_snapshot_success_at") is not None
    assert await cache.get_value("stats:last_gitcoin_success_at") is not None
    assert len(signals) == 1
    assert signals[0]["event_type"] == "proposal_new"
    assert signals[0]["severity"] == "high"
    assert await cache.get_counter("stats:signals_generated") == 1


def test_diff_snapshot_detects_vote_swing_and_result_flip():
    now = datetime(2026, 5, 26, tzinfo=UTC)
    previous = [
        {
            "id": "proposal-1",
            "title": "Treasury vote",
            "space": {"id": "base.eth", "name": "Base DAO"},
            "end": int((now + timedelta(days=3)).timestamp()),
            "scores": [80, 20],
            "scores_total": 100,
            "votes": 12,
            "quorum": 80,
        }
    ]
    current = [
        {
            **previous[0],
            "scores": [35, 65],
            "scores_total": 100,
            "votes": 20,
        }
    ]

    events = poller.diff_snapshot_proposals(previous, current, now=now)

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "proposal_changed"
    assert event["vote_swing_pct"] == 45
    assert event["for_vs_against_swing"] is True
    assert event["current"]["current_result"] == "failing"


def test_diff_snapshot_detects_deadline_threshold_crossing():
    previous_poll_time = datetime(2026, 5, 26, 0, 0, tzinfo=UTC)
    now = datetime(2026, 5, 26, 2, 0, tzinfo=UTC)
    proposal = {
        "id": "proposal-1",
        "title": "Deadline vote",
        "space": {"id": "base.eth", "name": "Base DAO"},
        "end": int((previous_poll_time + timedelta(hours=73)).timestamp()),
        "scores": [55, 45],
        "scores_total": 100,
        "votes": 10,
        "quorum": 0,
    }

    events = poller.diff_snapshot_proposals(
        [proposal],
        [proposal],
        now=now,
        previous_poll_time=previous_poll_time,
    )

    assert [event["event_type"] for event in events] == ["proposal_deadline_approaching"]


async def test_process_diff_events_discards_low_score_noise():
    generated = await poller.process_diff_events(
        [
            {
                "event_id": "low-event",
                "event_type": "grant_new",
                "source": "gitcoin",
                "protocol": "Gitcoin",
                "title": "Small maintenance round",
                "is_new_grant": True,
                "hours_until_deadline": 999_999,
                "estimated_treasury_impact_usd": 0,
            }
        ],
        now=datetime(2026, 5, 26, tzinfo=UTC),
    )

    assert generated == []
    assert await cache.get_counter("stats:signals_ignored") == 1


async def test_process_diff_events_suppresses_duplicates_before_enrichment(monkeypatch):
    now = datetime(2026, 5, 26, tzinfo=UTC)
    existing_signal = {
        "event_id": "duplicate-event",
        "event_type": "proposal_changed",
        "source": "snapshot",
        "protocol": "Base DAO",
        "title": "Duplicate vote shift",
        "severity": "high",
        "urgency_score": 60,
    }
    await store.save_signal(existing_signal, now=now)

    async def fail_enrichment(*args, **kwargs):
        raise AssertionError("duplicate signals should not reach enrichment")

    monkeypatch.setattr(poller, "enrich_signal", fail_enrichment)

    generated = await poller.process_diff_events(
        [
            {
                "event_id": "duplicate-event",
                "event_type": "proposal_changed",
                "source": "snapshot",
                "protocol": "Base DAO",
                "title": "Duplicate vote shift",
                "vote_swing_pct": 21,
                "estimated_treasury_impact_usd": 200_000,
            }
        ],
        now=now,
    )

    assert generated == []
    assert await cache.get_counter("stats:signals_duplicates_suppressed") == 1


async def test_poll_ecosystem_ingests_social_signals(monkeypatch):
    proposal = {
        "id": "proposal-1",
        "title": "Fund Base public goods",
        "body": "Allocate $250k to builders.",
        "space": {"id": "base.eth", "name": "Base DAO"},
        "end": int((datetime.now(UTC) + timedelta(days=2)).timestamp()),
        "scores": [75, 25],
        "scores_total": 100,
        "votes": 10,
        "quorum": 150,
    }
    social_cast = {
        "hash": "cast-social-1",
        "text": "Base governance vote is accelerating and builders are paying attention.",
        "timestamp": datetime.now(UTC).isoformat(),
        "author": {
            "fid": 77,
            "username": "ecosystemwatch",
            "display_name": "Ecosystem Watch",
            "follower_count": 2500,
            "score": 0.93,
            "verified_accounts": [{"platform": "x", "username": "ecosystemwatch"}],
        },
        "reactions": {"likes_count": 22, "recasts_count": 6},
        "replies": {"count": 5},
        "channel": {"id": "base", "name": "Base"},
    }
    social_event = {
        "event_id": "social-1",
        "event_type": "social_governance_momentum",
        "source": "farcaster",
        "protocol": "Base",
        "title": "Base governance discussion accelerating",
        "source_url": "https://warpcast.com/~/channel/base",
        "severity": "high",
        "urgency_score": 76,
        "importance_score": 34,
        "reasons": ["mention velocity is above 3 per window"],
        "score_components": [{"rule": "mention_velocity_gt_3", "points": 18}],
        "requires_llm_reasoning": True,
        "notify_users": False,
        "store_as_major_signal": True,
        "dashboard_worthy": True,
        "escalation_recommendation": "priority_digest",
        "mention_velocity": 4.5,
        "engagement_spike": 18.0,
        "repeated_reference_count": 4,
        "verified_actor_count": 1,
        "governance_activity_score": 14.0,
        "launch_momentum_score": 0.0,
        "social_attention_score": 28.0,
        "current": {"cast_count": 1, "unique_authors": 1},
        "previous": None,
    }

    async def fake_fetch_active_proposals():
        return [proposal]

    async def fake_fetch_active_grants():
        return []

    async def fake_fetch_social_casts(*args, **kwargs):
        return [social_cast]

    async def fake_normalize_social_casts(*args, **kwargs):
        return [social_event]

    monkeypatch.setattr(poller, "fetch_active_proposals", fake_fetch_active_proposals)
    monkeypatch.setattr(poller, "fetch_active_grants", fake_fetch_active_grants)
    monkeypatch.setattr(poller, "fetch_social_casts", fake_fetch_social_casts)
    monkeypatch.setattr(poller, "normalize_social_casts", fake_normalize_social_casts)
    monkeypatch.setattr(poller, "snapshot_fetch_ok", lambda: True)
    monkeypatch.setattr(poller, "gitcoin_fetch_ok", lambda: True)
    monkeypatch.setattr(poller, "neynar_fetch_ok", lambda: True)

    signals = await poller.poll_ecosystem()

    assert any(signal["source"] == "farcaster" for signal in signals)
    assert await cache.get_value("stats:last_farcaster_success_at") is not None
    assert await cache.get_counter("stats:social_events_generated") >= 1
    assert await cache.get_counter("stats:momentum_signals_generated") >= 1
