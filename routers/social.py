from __future__ import annotations

import logging

from fastapi import APIRouter

from cache import increment_counter
from models import SignalFeedResponse
from signals.feed import build_signal_feed

router = APIRouter(tags=["signals"])
logger = logging.getLogger(__name__)


@router.post("/social", response_model=SignalFeedResponse)
async def social_signal_feed() -> SignalFeedResponse:
    payload = await build_signal_feed(category="social", limit=10, premium=False)
    await increment_counter("stats:queries_served")
    await increment_counter("stats:social_feed_reads")
    logger.info(
        "Social signal feed served.",
        extra={"signals_count": payload["signals_count"], "quiet_period": payload["quiet_period"]},
    )
    return SignalFeedResponse.model_validate(payload)
