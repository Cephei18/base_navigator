from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from redis.exceptions import RedisError

from cache import get_client, get_value, mark_redis_unavailable, set_value
from config import get_settings
from signals.store import increment_stat

logger = logging.getLogger(__name__)

DISTRIBUTION_FEED_KEY = "signals:distribution"
DISTRIBUTION_MEMORY_KEY = "state:distribution:published"
DISTRIBUTION_COOLDOWN_SECONDS = 6 * 60 * 60
DISTRIBUTION_MAX_ITEMS = 50


@dataclass(frozen=True)
class DistributionResult:
    published: bool
    reason: str
    payload: dict[str, Any] | None = None
    external_posted: bool = False


async def publish_signal(signal: dict[str, Any], *, now: datetime | None = None) -> DistributionResult:
    current_time = now or datetime.now(UTC)
    if not should_publish_signal(signal):
        await increment_stat("distribution_skips")
        return DistributionResult(published=False, reason="not_eligible")

    fingerprint = _signal_fingerprint(signal)
    memory = await _load_memory()
    previous = _parse_datetime(memory["fingerprints"].get(fingerprint))
    if previous is not None and current_time - previous < timedelta(seconds=_cooldown_seconds()):
        await increment_stat("distribution_cooldown_suppressions")
        return DistributionResult(published=False, reason="cooldown_suppressed")

    message = build_distribution_message(signal)
    payload = {
        "event_id": signal.get("event_id"),
        "event_type": signal.get("event_type"),
        "source": signal.get("source"),
        "protocol": signal.get("protocol"),
        "severity": signal.get("severity"),
        "urgency_score": signal.get("urgency_score"),
        "message": message,
        "published_at": current_time.isoformat(),
        "channel": "farcaster",
        "target": "Base community",
        "external_posted": False,
    }

    external_posted = False
    if await _can_post_externally(signal):
        try:
            external_posted = await _post_to_farcaster(message)
        except Exception as exc:
            logger.warning(
                "Farcaster publication failed.",
                extra={"event_id": signal.get("event_id"), "error": f"{type(exc).__name__}: {exc}"},
            )
    payload["external_posted"] = external_posted

    await _write_distribution(payload)
    memory["fingerprints"][fingerprint] = current_time.isoformat()
    await _save_memory(_prune_memory(memory, current_time))
    await increment_stat("signals_distributed")
    await set_value("stats:last_signal_distributed_at", current_time.isoformat())
    return DistributionResult(published=True, reason="published", payload=payload, external_posted=external_posted)


async def list_published_signals(limit: int = 10) -> list[dict[str, Any]]:
    limit = max(0, min(limit, DISTRIBUTION_MAX_ITEMS))
    if limit == 0:
        return []

    client = await get_client()
    if client is not None:
        try:
            items = await client.lrange(DISTRIBUTION_FEED_KEY, 0, limit - 1)
            return [decoded for decoded in (_decode_payload(item) for item in items) if decoded is not None]
        except RedisError as exc:
            await mark_redis_unavailable(exc)

    values = await get_value(DISTRIBUTION_FEED_KEY)
    if not isinstance(values, list):
        return []
    return [item for item in values[:limit] if isinstance(item, dict)]


def should_publish_signal(signal: dict[str, Any]) -> bool:
    severity = str(signal.get("severity") or "").lower()
    source = str(signal.get("source") or "").lower()
    score = int(signal.get("urgency_score") or 0)
    return bool(
        severity == "critical"
        or (severity == "high" and source == "farcaster" and bool(signal.get("store_as_major_signal")))
        or score >= 70
        or signal.get("notify_users") is True
        or signal.get("distribution_priority") in {"announce", "immediate_alert"}
    )


def build_distribution_message(signal: dict[str, Any]) -> str:
    severity = str(signal.get("severity") or "low").lower()
    protocol = str(signal.get("protocol") or "Base")
    event_type = str(signal.get("event_type") or "").lower()
    title = str(signal.get("title") or protocol).strip()
    source = str(signal.get("source") or "").lower()
    source_url = str(signal.get("source_url") or "").strip()
    current = signal.get("current") if isinstance(signal.get("current"), dict) else {}

    if source == "farcaster" or event_type.startswith("social"):
        velocity = current.get("cast_count") or signal.get("repeated_reference_count") or 0
        return _truncate(
            f"🚨 {title}. Base attention is moving quickly across {velocity} casts."
            + (f" {source_url}" if source_url else "")
        )

    if severity == "critical":
        swing = signal.get("vote_swing_pct")
        deadline = signal.get("hours_until_deadline")
        impact = signal.get("estimated_treasury_impact_usd")
        details = [f"🚨 {title}."]
        if swing is not None:
            details.append(f"Vote swing: {swing}%.")
        if deadline is not None:
            details.append(f"{deadline}h remaining.")
        if impact:
            details.append(f"Potential treasury impact: ${_format_amount(impact)}.")
        if source_url:
            details.append(source_url)
        return _truncate(" ".join(details))

    if severity == "high":
        parts = [f"⚠️ {title}.", f"{protocol} signal remains elevated."]
        if signal.get("urgency_score") is not None:
            parts.append(f"Score {signal.get('urgency_score')}.")
        if source_url:
            parts.append(source_url)
        return _truncate(" ".join(parts))

    return _truncate(f"{title} / {protocol} / {severity}")


async def _write_distribution(payload: dict[str, Any]) -> None:
    client = await get_client()
    encoded = json.dumps(payload, default=str)
    if client is not None:
        try:
            await client.lpush(DISTRIBUTION_FEED_KEY, encoded)
            await client.ltrim(DISTRIBUTION_FEED_KEY, 0, DISTRIBUTION_MAX_ITEMS - 1)
            return
        except RedisError as exc:
            await mark_redis_unavailable(exc)

    values = await get_value(DISTRIBUTION_FEED_KEY)
    if not isinstance(values, list):
        values = []
    values.insert(0, payload)
    await set_value(DISTRIBUTION_FEED_KEY, values[:DISTRIBUTION_MAX_ITEMS])


async def _load_memory() -> dict[str, dict[str, str]]:
    memory = await get_value(DISTRIBUTION_MEMORY_KEY)
    if not isinstance(memory, dict):
        return {"fingerprints": {}}
    fingerprints = memory.get("fingerprints")
    if not isinstance(fingerprints, dict):
        return {"fingerprints": {}}
    return {"fingerprints": {str(key): str(value) for key, value in fingerprints.items()}}


async def _save_memory(memory: dict[str, dict[str, str]]) -> None:
    await set_value(DISTRIBUTION_MEMORY_KEY, memory)


async def _post_to_farcaster(message: str) -> bool:
    settings = get_settings()
    if not settings.neynar_api_key or not settings.farcaster_signer_uuid:
        return False

    url = f"{settings.neynar_api_base_url.rstrip('/')}/v2/farcaster/cast"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            headers={"x-api-key": settings.neynar_api_key},
            json={"signer_uuid": settings.farcaster_signer_uuid, "text": message},
        )
        response.raise_for_status()
    logger.info("Published Farcaster cast.")
    return True


async def _can_post_externally(signal: dict[str, Any]) -> bool:
    settings = get_settings()
    if not settings.neynar_api_key or not settings.farcaster_signer_uuid:
        return False
    if signal.get("publish_to_farcaster") is False:
        return False
    return should_publish_signal(signal)


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


def _prune_memory(memory: dict[str, dict[str, str]], now: datetime) -> dict[str, dict[str, str]]:
    cutoff = now - timedelta(seconds=_cooldown_seconds())
    fingerprints = {
        fingerprint: timestamp
        for fingerprint, timestamp in memory["fingerprints"].items()
        if (_parse_datetime(timestamp) or now) >= cutoff
    }
    return {"fingerprints": fingerprints}


def _cooldown_seconds() -> int:
    settings = get_settings()
    return settings.farcaster_distribution_cooldown_seconds or DISTRIBUTION_COOLDOWN_SECONDS


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _decode_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid distribution payload in Redis.", extra={"payload_value": value})
        return None
    return decoded if isinstance(decoded, dict) else None


def _truncate(value: str, limit: int = 320) -> str:
    return value[:limit]


def _format_amount(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric >= 1_000_000:
        return f"{numeric / 1_000_000:.1f}M"
    if numeric >= 1_000:
        return f"{numeric / 1_000:.1f}k"
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}"
