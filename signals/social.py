from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

BASE_KEYWORDS = {
    "base",
    "base dao",
    "base chain",
    "base app",
    "base ecosystem",
    "on base",
}
_GOVERNANCE_KEYWORDS = {
    "governance",
    "proposal",
    "vote",
    "quorum",
    "snapshot",
    "dao",
}
_LAUNCH_KEYWORDS = {
    "launch",
    "launched",
    "launching",
    "mainnet",
    "announcing",
    "announcement",
    "release",
    "shipping",
}
_FUNDING_KEYWORDS = {
    "grant",
    "grants",
    "funding",
    "fund",
    "round",
    "treasury",
    "builder",
    "builders",
}

_SOCIAL_EVENT_TYPES = {
    "general": "social_momentum",
    "governance": "social_governance_momentum",
    "launch": "social_launch_momentum",
    "funding": "social_funding_visibility",
}


async def normalize_social_casts(
    casts: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    window_minutes: int = 240,
) -> list[dict[str, Any]]:
    current_time = now or datetime.now(UTC)
    window_started_at = current_time - timedelta(minutes=max(1, window_minutes))
    records = [
        record
        for record in (_cast_record(cast, current_time) for cast in casts)
        if record is not None and record["timestamp"] >= window_started_at
    ]
    if not records:
        return []

    topic_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        for topic in _classify_topics(record["text"]):
            topic_records[topic].append(record)

    events: list[dict[str, Any]] = []
    for topic in ("general", "governance", "launch", "funding"):
        topic_casts = topic_records.get(topic, [])
        event = _build_topic_event(
            topic,
            topic_casts,
            current_time=current_time,
            window_minutes=window_minutes,
        )
        if event is not None:
            events.append(event)

    events.sort(key=lambda item: (-int(item.get("social_attention_score") or 0), str(item.get("event_type") or "")))
    return events


def _build_topic_event(
    topic: str,
    topic_casts: list[dict[str, Any]],
    *,
    current_time: datetime,
    window_minutes: int,
) -> dict[str, Any] | None:
    if not topic_casts:
        return None

    cast_count = len(topic_casts)
    unique_authors = len({cast.get("author_fid") or cast.get("author_username") for cast in topic_casts if cast.get("author_fid") or cast.get("author_username")})
    verified_actor_count = sum(1 for cast in topic_casts if cast.get("author_verified"))
    governance_count = sum(1 for cast in topic_casts if topic == "governance")
    launch_count = sum(1 for cast in topic_casts if topic == "launch")
    funding_count = sum(1 for cast in topic_casts if topic == "funding")
    engagement_total = round(sum(cast.get("engagement_score", 0.0) for cast in topic_casts), 2)
    engagement_spike = round(engagement_total / max(1, cast_count), 2)
    mention_velocity = round(cast_count / max(1.0, window_minutes / 60.0), 2)
    repeated_reference_count = cast_count

    governance_activity_score = round(
        governance_count * 4 + unique_authors * 1.5 + verified_actor_count * 2 + min(engagement_total / 8.0, 20.0),
        2,
    )
    launch_momentum_score = round(
        launch_count * 4 + unique_authors * 1.5 + verified_actor_count * 2 + min(engagement_total / 8.0, 20.0),
        2,
    )
    social_attention_score = round(
        mention_velocity * 4 + engagement_spike + unique_authors * 2 + verified_actor_count * 2,
        2,
    )
    if topic == "governance":
        social_attention_score = round(social_attention_score + governance_activity_score, 2)
    elif topic == "launch":
        social_attention_score = round(social_attention_score + launch_momentum_score, 2)
    elif topic == "funding":
        social_attention_score = round(social_attention_score + funding_count * 5 + min(engagement_total / 10.0, 15.0), 2)

    score_threshold = 8 if topic == "general" else 10
    if social_attention_score < score_threshold and verified_actor_count == 0 and unique_authors < 2:
        return None

    event_type = _SOCIAL_EVENT_TYPES[topic]
    payload = {
        "source": "farcaster",
        "event_type": event_type,
        "protocol": "Base",
        "title": _build_title(topic, cast_count),
        "source_url": "https://warpcast.com/~/channel/base",
        "mention_velocity": mention_velocity,
        "engagement_spike": engagement_spike,
        "repeated_reference_count": repeated_reference_count,
        "verified_actor_count": verified_actor_count,
        "governance_activity_score": governance_activity_score,
        "launch_momentum_score": launch_momentum_score,
        "social_attention_score": social_attention_score,
        "force_llm_reasoning": topic in {"governance", "launch", "funding"} and social_attention_score >= 18,
        "current": {
            "window_started_at": (current_time - timedelta(minutes=max(1, window_minutes))).isoformat(),
            "window_minutes": window_minutes,
            "cast_count": cast_count,
            "unique_authors": unique_authors,
            "verified_actor_count": verified_actor_count,
            "engagement_total": engagement_total,
            "topic": topic,
            "top_casts": [
                {
                    "hash": cast.get("hash"),
                    "text": cast.get("text"),
                    "author_username": cast.get("author_username"),
                    "engagement_score": cast.get("engagement_score"),
                }
                for cast in topic_casts[:3]
            ],
        },
        "previous": None,
    }
    payload["event_id"] = _event_id(payload, topic_casts)
    return payload


def _cast_record(cast: dict[str, Any], current_time: datetime) -> dict[str, Any] | None:
    cast_hash = str(cast.get("hash") or cast.get("cast_hash") or "")
    text = str(cast.get("text") or "").strip()
    if not cast_hash or not text:
        return None

    timestamp = _parse_timestamp(cast.get("timestamp")) or current_time
    author = cast.get("author") if isinstance(cast.get("author"), dict) else {}
    reactions = cast.get("reactions") if isinstance(cast.get("reactions"), dict) else {}
    replies = cast.get("replies") if isinstance(cast.get("replies"), dict) else {}
    channel = cast.get("channel") if isinstance(cast.get("channel"), dict) else {}

    likes_count = _number(reactions.get("likes_count"))
    recasts_count = _number(reactions.get("recasts_count"))
    replies_count = _number(replies.get("count"))
    follower_count = _number(author.get("follower_count"))
    author_score = _number(author.get("score"))
    verified_accounts = author.get("verified_accounts") if isinstance(author.get("verified_accounts"), list) else []
    author_verified = bool(verified_accounts)
    engagement_score = round(likes_count + recasts_count * 2 + replies_count * 1.5 + min(follower_count / 1000.0, 10.0), 2)

    return {
        "hash": cast_hash,
        "text": text,
        "timestamp": timestamp,
        "author_fid": author.get("fid"),
        "author_username": str(author.get("username") or "").lower(),
        "author_display_name": str(author.get("display_name") or ""),
        "author_score": author_score,
        "author_verified": author_verified,
        "likes_count": likes_count,
        "recasts_count": recasts_count,
        "replies_count": replies_count,
        "engagement_score": engagement_score,
        "channel_id": str(channel.get("id") or "").lower(),
        "channel_name": str(channel.get("name") or "").lower(),
    }


def _classify_topics(text: str) -> set[str]:
    lowered = text.lower()
    topics: set[str] = set()

    if any(keyword in lowered for keyword in BASE_KEYWORDS):
        topics.add("general")
    if any(keyword in lowered for keyword in _GOVERNANCE_KEYWORDS):
        topics.add("governance")
    if any(keyword in lowered for keyword in _LAUNCH_KEYWORDS):
        topics.add("launch")
    if any(keyword in lowered for keyword in _FUNDING_KEYWORDS):
        topics.add("funding")

    if not topics and "base" in lowered:
        topics.add("general")
    return topics


def _build_title(topic: str, cast_count: int) -> str:
    if topic == "governance":
        return f"Base governance discussion accelerating across {cast_count} casts"
    if topic == "launch":
        return f"Base launch momentum rising across {cast_count} casts"
    if topic == "funding":
        return f"Base funding visibility increasing across {cast_count} casts"
    return f"Base ecosystem attention rising across {cast_count} casts"


def _event_id(payload: dict[str, Any], topic_casts: list[dict[str, Any]]) -> str:
    fingerprint = {
        "event_type": payload.get("event_type"),
        "source": payload.get("source"),
        "protocol": payload.get("protocol"),
        "title": payload.get("title"),
        "hashes": [cast.get("hash") for cast in topic_casts[:10]],
        "scores": {
            "mention_velocity": payload.get("mention_velocity"),
            "engagement_spike": payload.get("engagement_spike"),
            "social_attention_score": payload.get("social_attention_score"),
        },
    }
    digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, default=str).encode()).hexdigest()
    return f"social:{digest[:16]}"


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
