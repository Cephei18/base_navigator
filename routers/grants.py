from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from cache import get_cached, increment_counter, set_cached, set_value
from config import get_settings
from fetchers.gitcoin import fetch_active_grants
from models import GrantsResponse, SignalFeedResponse
from signals.feed import build_signal_feed, empty_feed_response
from synthesis.grants import synthesize_grants

router = APIRouter(tags=["grants"])
logger = logging.getLogger(__name__)


@router.post("/grants", response_model=SignalFeedResponse)
async def grants_intelligence(
    refresh: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SignalFeedResponse:
    settings = get_settings()
    feed = await build_signal_feed(category="grants", limit=limit, premium=False)
    if feed["signals"]:
        await increment_counter("stats:queries_served")
        logger.info(
            "Grants intelligence served from signal feed.",
            extra={"signals_count": feed["signals_count"], "refresh": refresh},
        )
        return SignalFeedResponse.model_validate(feed)

    if not settings.allow_live_fallback:
        await increment_counter("stats:queries_served")
        payload = empty_feed_response(category="grants")
        logger.info("Grants signal feed quiet period.", extra={"refresh": refresh})
        return SignalFeedResponse.model_validate(payload)

    cache_key = "cache:grants:v1"

    if not refresh:
        cached = await get_cached(cache_key)
        if cached is not None:
            await increment_counter("stats:queries_served")
            return _fallback_response(cached, refresh=refresh)

    grants = await fetch_active_grants()
    result = await synthesize_grants(grants)
    payload = GrantsResponse.model_validate(result).model_dump(mode="json")

    await set_cached(cache_key, payload, settings.grants_cache_ttl)
    await set_value("stats:last_grants_update", datetime.now(UTC).isoformat())
    await increment_counter("stats:queries_served")
    logger.info(
        "Grants intelligence generated.",
        extra={"grant_count": len(payload["open_grants"]), "refresh": refresh},
    )
    return _fallback_response(payload, refresh=refresh)


def _fallback_response(payload: dict, *, refresh: bool) -> SignalFeedResponse:
    response = empty_feed_response(category="grants", source="live_fallback")
    response["quiet_period"] = False
    response["message"] = "Live fallback used because no precomputed grants signals exist."
    response["live_fallback"] = payload
    response["signals_count"] = len(payload.get("open_grants", []))
    response["severity_summary"] = {
        "urgent": len(payload.get("urgent_deadlines", [])),
    }
    logger.info(
        "Grants live fallback used.",
        extra={"fallback_items": response["signals_count"], "refresh": refresh},
    )
    return SignalFeedResponse.model_validate(response)
