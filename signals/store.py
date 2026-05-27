from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.exceptions import RedisError

from cache import (
    get_client,
    get_counter,
    get_value,
    increment_counter,
    mark_redis_unavailable,
    set_value,
)

logger = logging.getLogger(__name__)

SIGNAL_FEED_KEY = "signals:feed"
SIGNAL_MEMORY_KEY = "state:signals:latest"
SIGNAL_FEED_MAX_ITEMS = 50
SIGNAL_COOLDOWN_SECONDS = 6 * 60 * 60


@dataclass(frozen=True)
class SaveSignalResult:
    saved: bool
    reason: str


async def save_signal(
    signal: dict[str, Any],
    *,
    cooldown_seconds: int = SIGNAL_COOLDOWN_SECONDS,
    now: datetime | None = None,
) -> bool:
    result = await save_signal_with_result(
        signal,
        cooldown_seconds=cooldown_seconds,
        now=now,
    )
    return result.saved


async def save_signal_with_result(
    signal: dict[str, Any],
    *,
    cooldown_seconds: int = SIGNAL_COOLDOWN_SECONDS,
    now: datetime | None = None,
) -> SaveSignalResult:
    current_time = now or datetime.now(UTC)
    fingerprint = _signal_fingerprint(signal)
    memory = await _load_memory()
    if _in_cooldown(memory, fingerprint, current_time, cooldown_seconds):
        await increment_stat("signals_duplicates_suppressed")
        return SaveSignalResult(saved=False, reason="duplicate_cooldown")

    await _write_signal(signal)
    memory["fingerprints"][fingerprint] = current_time.isoformat()
    await _save_memory(_prune_memory(memory, current_time, cooldown_seconds))
    await _record_saved_signal_stats(signal, current_time)
    return SaveSignalResult(saved=True, reason="stored")


async def get_signals(limit: int = 10) -> list[dict[str, Any]]:
    limit = max(0, min(limit, SIGNAL_FEED_MAX_ITEMS))
    if limit == 0:
        return []

    client = await get_client()
    if client is not None:
        try:
            items = await client.lrange(SIGNAL_FEED_KEY, 0, limit - 1)
            signals: list[dict[str, Any]] = []
            for item in items:
                decoded = _decode_signal(item)
                if decoded is not None:
                    signals.append(decoded)
            return signals
        except RedisError as exc:
            await mark_redis_unavailable(exc)

    signals = await get_value(SIGNAL_FEED_KEY)
    if not isinstance(signals, list):
        return []
    return [signal for signal in signals[:limit] if isinstance(signal, dict)]


async def get_signal_by_id(event_id: str) -> dict[str, Any] | None:
    for signal in await get_signals(SIGNAL_FEED_MAX_ITEMS):
        if signal.get("event_id") == event_id:
            return signal
    return None


async def get_signal_store_size() -> int:
    client = await get_client()
    if client is not None:
        try:
            return int(await client.llen(SIGNAL_FEED_KEY))
        except RedisError as exc:
            await mark_redis_unavailable(exc)

    signals = await get_value(SIGNAL_FEED_KEY)
    return len(signals) if isinstance(signals, list) else 0


async def signal_in_cooldown(
    signal: dict[str, Any],
    *,
    cooldown_seconds: int = SIGNAL_COOLDOWN_SECONDS,
    now: datetime | None = None,
) -> bool:
    current_time = now or datetime.now(UTC)
    memory = await _load_memory()
    return _in_cooldown(
        memory,
        _signal_fingerprint(signal),
        current_time,
        cooldown_seconds,
    )


async def increment_stat(key: str, amount: int = 1) -> int:
    return await increment_counter(_stat_key(key), amount=amount)


async def get_stat(key: str) -> int:
    return await get_counter(_stat_key(key))


async def _write_signal(signal: dict[str, Any]) -> None:
    client = await get_client()
    encoded = json.dumps(signal, default=str)
    if client is not None:
        try:
            await client.lpush(SIGNAL_FEED_KEY, encoded)
            await client.ltrim(SIGNAL_FEED_KEY, 0, SIGNAL_FEED_MAX_ITEMS - 1)
            return
        except RedisError as exc:
            await mark_redis_unavailable(exc)

    signals = await get_value(SIGNAL_FEED_KEY)
    if not isinstance(signals, list):
        signals = []
    signals.insert(0, signal)
    await set_value(SIGNAL_FEED_KEY, signals[:SIGNAL_FEED_MAX_ITEMS])


async def _record_saved_signal_stats(signal: dict[str, Any], now: datetime) -> None:
    severity = str(signal.get("severity") or "unknown")
    await increment_stat("signals_generated")
    await increment_stat(f"signals_{severity}_severity")
    if severity in {"high", "critical"}:
        await increment_stat("signals_high_severity")
    if signal.get("requires_llm_reasoning"):
        await increment_stat("signals_escalated")
    if signal.get("notify_users"):
        await increment_stat("signals_notification_ready")
    await set_value("stats:last_signal_generated_at", now.isoformat())


async def _load_memory() -> dict[str, dict[str, str]]:
    memory = await get_value(SIGNAL_MEMORY_KEY)
    if not isinstance(memory, dict):
        return {"fingerprints": {}}
    fingerprints = memory.get("fingerprints")
    if not isinstance(fingerprints, dict):
        return {"fingerprints": {}}
    return {"fingerprints": {str(key): str(value) for key, value in fingerprints.items()}}


async def _save_memory(memory: dict[str, dict[str, str]]) -> None:
    await set_value(SIGNAL_MEMORY_KEY, memory)


def _prune_memory(
    memory: dict[str, dict[str, str]],
    now: datetime,
    cooldown_seconds: int,
) -> dict[str, dict[str, str]]:
    cutoff = now - timedelta(seconds=cooldown_seconds)
    fingerprints = {
        fingerprint: timestamp
        for fingerprint, timestamp in memory["fingerprints"].items()
        if (_parse_datetime(timestamp) or now) >= cutoff
    }
    return {"fingerprints": fingerprints}


def _in_cooldown(
    memory: dict[str, dict[str, str]],
    fingerprint: str,
    now: datetime,
    cooldown_seconds: int,
) -> bool:
    previous = _parse_datetime(memory["fingerprints"].get(fingerprint))
    if previous is None:
        return False
    return now - previous < timedelta(seconds=cooldown_seconds)


def _signal_fingerprint(signal: dict[str, Any]) -> str:
    event_id = signal.get("event_id")
    if event_id:
        return str(event_id)
    payload = {
        "source": signal.get("source"),
        "event_type": signal.get("event_type"),
        "protocol": signal.get("protocol"),
        "title": signal.get("title"),
        "score": signal.get("urgency_score"),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _decode_signal(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid signal payload in Redis.", extra={"signal_value": value})
        return None
    return decoded if isinstance(decoded, dict) else None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _stat_key(key: str) -> str:
    return key if key.startswith("stats:") else f"stats:{key}"
