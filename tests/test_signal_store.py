from __future__ import annotations

from datetime import UTC, datetime, timedelta

from signals import store


def _signal(event_id: str, *, severity: str = "medium", score: int = 42) -> dict:
    return {
        "event_id": event_id,
        "event_type": "proposal_changed",
        "source": "snapshot",
        "protocol": "Example DAO",
        "title": "Treasury vote",
        "severity": severity,
        "urgency_score": score,
        "requires_llm_reasoning": score >= 30,
        "notify_users": score >= 70,
    }


async def test_save_signal_stores_latest_items_and_updates_stats():
    first = _signal("event-1", severity="medium", score=42)
    second = _signal("event-2", severity="critical", score=75)

    assert await store.save_signal(first) is True
    assert await store.save_signal(second) is True

    signals = await store.get_signals(limit=10)

    assert [signal["event_id"] for signal in signals] == ["event-2", "event-1"]
    assert await store.get_signal_by_id("event-1") == first
    assert await store.get_stat("signals_generated") == 2
    assert await store.get_stat("signals_high_severity") == 1
    assert await store.get_stat("signals_notification_ready") == 1


async def test_save_signal_suppresses_duplicates_inside_cooldown():
    now = datetime(2026, 5, 26, tzinfo=UTC)
    signal = _signal("event-1")

    first = await store.save_signal_with_result(signal, now=now)
    second = await store.save_signal_with_result(signal, now=now + timedelta(minutes=5))

    assert first.saved is True
    assert second.saved is False
    assert second.reason == "duplicate_cooldown"
    assert len(await store.get_signals(limit=10)) == 1
    assert await store.get_stat("signals_duplicates_suppressed") == 1


async def test_save_signal_allows_duplicate_after_cooldown_expires():
    now = datetime(2026, 5, 26, tzinfo=UTC)
    signal = _signal("event-1")

    assert await store.save_signal(signal, cooldown_seconds=60, now=now) is True
    assert (
        await store.save_signal(signal, cooldown_seconds=60, now=now + timedelta(seconds=61))
        is True
    )

    assert len(await store.get_signals(limit=10)) == 2


async def test_signal_feed_is_trimmed_to_max_items():
    for index in range(store.SIGNAL_FEED_MAX_ITEMS + 5):
        assert await store.save_signal(_signal(f"event-{index}")) is True

    signals = await store.get_signals(limit=store.SIGNAL_FEED_MAX_ITEMS)

    assert len(signals) == store.SIGNAL_FEED_MAX_ITEMS
    assert signals[0]["event_id"] == "event-54"
    assert signals[-1]["event_id"] == "event-5"
