from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from redis.exceptions import RedisError

from cache import get_client, get_value, set_value, mark_redis_unavailable, increment_counter

logger = logging.getLogger(__name__)

TIMELINE_TICKS_KEY = "timeline:signal:{signal_id}:ticks"
TIMELINE_LIFECYCLE_KEY = "timeline:lifecycle:{signal_id}"
TIMELINE_MAX_TICKS = 1000


@dataclass
class Tick:
    ts: str
    score: float
    reason: str


async def append_tick(signal_id: str, score: float, reason: str, ts: datetime | None = None) -> None:
    """Append a score tick for a signal. Stored newest-first (LPUSH semantics).

    Uses Redis when configured, otherwise uses in-memory fallback via `set_value`/`get_value`.
    """
    now = ts or datetime.now(timezone.utc)
    tick = {"ts": now.isoformat(), "score": float(score), "reason": reason}
    key = TIMELINE_TICKS_KEY.format(signal_id=signal_id)
    client = await get_client()
    encoded = json.dumps(tick, default=str)
    if client is not None:
        try:
            await client.lpush(key, encoded)
            await client.ltrim(key, 0, TIMELINE_MAX_TICKS - 1)
            await increment_counter("timeline:ticks_appended")
            return
        except RedisError as exc:
            await mark_redis_unavailable(exc)

    # fallback
    items = await get_value(key) or []
    if not isinstance(items, list):
        items = []
    items.insert(0, tick)
    await set_value(key, items[:TIMELINE_MAX_TICKS])
    await increment_counter("timeline:ticks_appended")


async def get_ticks(signal_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    key = TIMELINE_TICKS_KEY.format(signal_id=signal_id)
    client = await get_client()
    if client is not None:
        try:
            items = await client.lrange(key, 0, limit - 1)
            ticks: List[Dict[str, Any]] = []
            for item in items:
                if isinstance(item, str):
                    try:
                        ticks.append(json.loads(item))
                    except json.JSONDecodeError:
                        logger.warning("Invalid tick payload in Redis", extra={"value": item})
                elif isinstance(item, dict):
                    ticks.append(item)
            return ticks
        except RedisError as exc:
            await mark_redis_unavailable(exc)

    items = await get_value(key)
    if not isinstance(items, list):
        return []
    return items[:max(0, min(limit, len(items)))]


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


async def _window_aggregate(ticks: List[Dict[str, Any]], window_seconds: int, now: datetime | None = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    sel = [t for t in ticks if _parse_ts(t["ts"]) >= cutoff]
    count = len(sel)
    if count == 0:
        return {"count": 0, "sum": 0.0, "avg": 0.0, "first": None, "last": None}
    scores = [float(t["score"]) for t in sel]
    return {"count": count, "sum": sum(scores), "avg": sum(scores) / count, "first": sel[-1], "last": sel[0]}


async def compute_momentum(signal_id: str, now: datetime | None = None) -> Dict[str, Any]:
    """Return simple momentum metrics across 1h/6h/24h windows.

    Returns: {avg_1h, avg_6h, avg_24h, momentum_score, trend}
    """
    now = now or datetime.now(timezone.utc)
    ticks = await get_ticks(signal_id)
    w1 = await _window_aggregate(ticks, 3600, now)
    w2 = await _window_aggregate(ticks, 6 * 3600, now)
    w3 = await _window_aggregate(ticks, 24 * 3600, now)
    # momentum as difference between short and long window
    momentum_score = float(w1["avg"] - w3["avg"]) if w3["count"] > 0 else float(w1["avg"])
    # deterministic trend
    if w1["avg"] > w2["avg"] and w2["avg"] > w3["avg"] and momentum_score > 2.0:
        trend = "accelerating"
    elif w1["avg"] < w2["avg"] and w2["avg"] < w3["avg"] and momentum_score < -2.0:
        trend = "decelerating"
    elif abs(momentum_score) <= 2.0:
        trend = "steady"
    else:
        trend = "mixed"
    return {
        "avg_1h": w1["avg"],
        "avg_6h": w2["avg"],
        "avg_24h": w3["avg"],
        "momentum_score": momentum_score,
        "trend": trend,
        "counts": {"1h": w1["count"], "6h": w2["count"], "24h": w3["count"]},
    }


async def evaluate_lifecycle(signal_id: str, now: datetime | None = None) -> Tuple[str, Dict[str, Any]]:
    """Evaluate and persist lifecycle state for a signal.

    Returns: (state, transition_trace)
    """
    now = now or datetime.now(timezone.utc)
    ticks = await get_ticks(signal_id)
    momentum = await compute_momentum(signal_id, now)
    current_score = momentum["avg_1h"]

    # simple deterministic lifecycle rules
    prev = await get_value(TIMELINE_LIFECYCLE_KEY.format(signal_id=signal_id)) or {}
    prev_state = prev.get("state") or "dormant"

    trace = {
        "avg_1h": momentum["avg_1h"],
        "avg_6h": momentum["avg_6h"],
        "avg_24h": momentum["avg_24h"],
        "momentum_score": momentum["momentum_score"],
    }

    # rules
    state = prev_state
    if momentum["counts"]["6h"] == 0 and momentum["counts"]["24h"] == 0 and momentum["counts"]["1h"] > 0:
        state = "emerging"
    elif momentum["trend"] == "accelerating" and momentum["counts"]["1h"] >= 2:
        state = "accelerating"
    elif momentum["trend"] == "steady" and prev_state == "accelerating":
        state = "peaking"
    elif momentum["trend"] == "decelerating":
        state = "cooling"
    elif momentum["counts"]["24h"] == 0:
        state = "dormant"
    # keep previous otherwise

    if state != prev_state:
        transition = {
            "state": state,
            "last_transition_at": now.isoformat(),
            "transition_trace": trace,
            "previous_state": prev_state,
        }
        await set_value(TIMELINE_LIFECYCLE_KEY.format(signal_id=signal_id), transition)
        await increment_counter("timeline:transitions")
        return state, transition

    # update trace timestamp
    updated = {**prev, "transition_trace": trace}
    await set_value(TIMELINE_LIFECYCLE_KEY.format(signal_id=signal_id), updated)
    return state, updated
