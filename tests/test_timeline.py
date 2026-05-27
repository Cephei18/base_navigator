from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from signals import timeline


@pytest.mark.asyncio
async def test_append_and_get_ticks():
    sid = "test_signal_1"
    now = datetime.now(timezone.utc)
    await timeline.append_tick(sid, 10.0, "initial", ts=now - timedelta(minutes=90))
    await timeline.append_tick(sid, 20.0, "later", ts=now - timedelta(minutes=30))
    ticks = await timeline.get_ticks(sid)
    assert isinstance(ticks, list)
    assert len(ticks) >= 2
    assert float(ticks[0]["score"]) == 20.0


@pytest.mark.asyncio
async def test_momentum_and_lifecycle_transitions():
    sid = "test_signal_2"
    now = datetime.now(timezone.utc)
    # simulate rising scores: 3 ticks in last 2 hours
    await timeline.append_tick(sid, 10.0, "t1", ts=now - timedelta(hours=3))
    await timeline.append_tick(sid, 20.0, "t2", ts=now - timedelta(hours=2))
    await timeline.append_tick(sid, 40.0, "t3", ts=now - timedelta(minutes=50))
    await timeline.append_tick(sid, 60.0, "t4", ts=now - timedelta(minutes=10))

    mom = await timeline.compute_momentum(sid, now=now)
    assert "trend" in mom
    state, trace = await timeline.evaluate_lifecycle(sid, now=now)
    assert state in {"emerging", "accelerating", "peaking", "cooling", "dormant"}
    # ensure we recorded the transition trace
    assert "momentum_score" in trace.get("transition_trace", trace)
