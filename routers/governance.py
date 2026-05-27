from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from cache import get_cached, increment_counter, set_cached, set_value
from config import get_settings
from fetchers.snapshot import fetch_active_proposals
from models import GovernanceResponse, SignalFeedResponse
from signals.feed import build_signal_feed, empty_feed_response
from synthesis.governance import synthesize_governance

router = APIRouter(tags=["governance"])
logger = logging.getLogger(__name__)


@router.post("/governance", response_model=SignalFeedResponse)
async def governance_intelligence(
    refresh: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SignalFeedResponse:
    settings = get_settings()
    feed = await build_signal_feed(category="governance", limit=limit, premium=False)
    if feed["signals"]:
        await increment_counter("stats:queries_served")
        logger.info(
            "Governance intelligence served from signal feed.",
            extra={"signals_count": feed["signals_count"], "refresh": refresh},
        )
        return SignalFeedResponse.model_validate(feed)

    if not settings.allow_live_fallback:
        await increment_counter("stats:queries_served")
        payload = empty_feed_response(category="governance")
        logger.info("Governance signal feed quiet period.", extra={"refresh": refresh})
        return SignalFeedResponse.model_validate(payload)

    cache_key = "cache:governance:v1"

    if not refresh:
        cached = await get_cached(cache_key)
        if cached is not None:
            await increment_counter("stats:queries_served")
            return _fallback_response(cached, refresh=refresh)

    proposals = await fetch_active_proposals()
    result = await synthesize_governance(proposals)
    payload = GovernanceResponse.model_validate(result).model_dump(mode="json")

    await set_cached(cache_key, payload, settings.governance_cache_ttl)
    await set_value("stats:last_governance_update", datetime.now(UTC).isoformat())
    await increment_counter("stats:queries_served")
    logger.info(
        "Governance intelligence generated.",
        extra={"proposal_count": len(payload["active_proposals"]), "refresh": refresh},
    )
    return _fallback_response(payload, refresh=refresh)


def _fallback_response(payload: dict, *, refresh: bool) -> SignalFeedResponse:
    response = empty_feed_response(category="governance", source="live_fallback")
    response["quiet_period"] = False
    response["message"] = "Live fallback used because no precomputed governance signals exist."
    response["live_fallback"] = payload
    response["signals_count"] = len(payload.get("active_proposals", []))
    response["severity_summary"] = {
        "urgent": int(payload.get("urgent_count") or 0),
    }
    logger.info(
        "Governance live fallback used.",
        extra={"fallback_items": response["signals_count"], "refresh": refresh},
    )
    return SignalFeedResponse.model_validate(response)
