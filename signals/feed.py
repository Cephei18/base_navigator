from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal

from signals.store import get_signals

logger = logging.getLogger(__name__)

SignalCategory = Literal["all", "governance", "grants"]
QUIET_PERIOD_MESSAGE = "No high-priority ecosystem signals detected."

_GOVERNANCE_KEYWORDS = {
    "governance",
    "proposal",
    "vote",
    "quorum",
    "snapshot",
    "dao",
}
_GRANT_KEYWORDS = {
    "grant",
    "grants",
    "fund",
    "funding",
    "round",
    "builder",
    "builders",
    "batches",
    "gitcoin",
}


async def build_signal_feed(
    *,
    category: SignalCategory = "all",
    limit: int = 10,
    premium: bool = False,
) -> dict[str, Any]:
    candidates = await get_signals(limit=50)
    filtered = [signal for signal in candidates if signal_matches_category(signal, category)]
    limited = filtered[: max(0, min(limit, 50))]
    shaped = [shape_signal(signal, premium=premium) for signal in limited]
    severity_summary = dict(Counter(str(signal.get("severity") or "unknown") for signal in shaped))
    quiet_period = len(shaped) == 0

    logger.info(
        "API signal feed read.",
        extra={
            "category": category,
            "premium": premium,
            "signals_count": len(shaped),
            "quiet_period": quiet_period,
            "feed_candidates": len(candidates),
        },
    )

    return {
        "source": "precomputed",
        "generated_at": datetime.now(UTC).isoformat(),
        "category": category,
        "premium": premium,
        "signals_count": len(shaped),
        "quiet_period": quiet_period,
        "message": QUIET_PERIOD_MESSAGE if quiet_period else "Precomputed signals returned.",
        "severity_summary": severity_summary,
        "signals": shaped,
        "live_fallback": None,
    }


def signal_matches_category(signal: dict[str, Any], category: SignalCategory) -> bool:
    if category == "all":
        return True

    source = str(signal.get("source") or "").lower()
    event_type = str(signal.get("event_type") or "").lower()
    protocol = str(signal.get("protocol") or "").lower()
    title = str(signal.get("title") or "").lower()
    raw_event = signal.get("raw_event") if isinstance(signal.get("raw_event"), dict) else {}
    raw_source = str(raw_event.get("source") or "").lower()
    haystack = f"{source} {raw_source} {event_type} {protocol} {title}"

    if category == "governance":
        return source == "snapshot" or any(keyword in haystack for keyword in _GOVERNANCE_KEYWORDS)

    return (
        source in {"gitcoin", "base_batches"}
        or raw_source in {"gitcoin", "base_batches"}
        or any(keyword in haystack for keyword in _GRANT_KEYWORDS)
    )


def shape_signal(signal: dict[str, Any], *, premium: bool) -> dict[str, Any]:
    public_fields = {
        "event_id",
        "event_type",
        "source",
        "protocol",
        "title",
        "source_url",
        "severity",
        "urgency_score",
        "importance_score",
        "reasons",
        "requires_llm_reasoning",
        "notify_users",
        "store_as_major_signal",
        "dashboard_worthy",
        "escalation_recommendation",
        "created_at",
        "scoring_version",
        "llm_enrichment",
    }
    shaped = {key: signal[key] for key in public_fields if key in signal}
    if premium:
        for key in ("score_components", "raw_event"):
            if key in signal:
                shaped[key] = signal[key]
    return shaped


def empty_feed_response(
    *,
    category: SignalCategory,
    source: Literal["precomputed", "live_fallback"] = "precomputed",
    premium: bool = False,
) -> dict[str, Any]:
    return {
        "source": source,
        "generated_at": datetime.now(UTC).isoformat(),
        "category": category,
        "premium": premium,
        "signals_count": 0,
        "quiet_period": True,
        "message": QUIET_PERIOD_MESSAGE,
        "severity_summary": {},
        "signals": [],
        "live_fallback": None,
    }
